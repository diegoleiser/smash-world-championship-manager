"""Synthetic regression coverage for evidence-based narrative selection."""

import unittest

from narrative_stories import Story, player_stories, select_stories, tournament_stories
from narrative_generators import (
    _count_close_sets, _find_final_match, _rivalry_scoreline_sentence,
    generate_player_summary, generate_tournament_preview,
)


def event(number, winner='Alpha'):
    return dict(tournament_id=f'e{number}', tournament_number=number,
                tournament_date=f'2026-01-{number:02d}', winner=winner)


def appearance(number, player, placement):
    return dict(tournament_id=f'e{number}', player=player, placement=placement)


def match(number, index, first, second, winner, score=(2, 0), stage='bracket'):
    return dict(match_id=f'{number}-{index}', tournament_id=f'e{number}',
                player_1=first, player_2=second, winner=winner, stage=stage,
                player_1_score=score[0], player_2_score=score[1], score_known=True)


def text(stories):
    return ' '.join(select_stories(stories, limit=20))


class NarrativeStoryTests(unittest.TestCase):
    def test_placement_streak_and_title_drought_use_appearances(self):
        archive = dict(events=[event(i) for i in range(1, 7)],
                       appearances=[appearance(1, 'Alpha', 1)] +
                       [appearance(i, 'Alpha', 2) for i in range(3, 7)], matches=[])
        result = text(player_stories(archive, 'Alpha'))
        self.assertIn('4 consecutive recorded appearances', result)
        self.assertIn('WC 06', result)  # Titles use the event registry, not placements.
        archive['events'] = [event(1)] + [event(i, 'Beta') for i in range(2, 7)]
        self.assertIn('WC 01', text(player_stories(archive, 'Alpha')))

    def test_historical_recap_cannot_use_future_results(self):
        archive = dict(events=[event(i, 'Beta') for i in range(1, 6)],
                       appearances=[appearance(i, 'Alpha', 2) for i in range(1, 6)], matches=[])
        self.assertNotIn('runner-up', text(tournament_stories(archive, 2)))
        self.assertIn('3 consecutive', text(tournament_stories(archive, 3)))
        self.assertNotIn('5 consecutive', text(tournament_stories(archive, 3)))

    def test_matchup_contrast_requires_repeated_evidence_and_rating_gap(self):
        archive = dict(events=[event(1)], appearances=[appearance(1, 'Alpha', 4)],
                       matches=[match(1, i, 'Alpha', 'Beta', 'Alpha' if i < 4 else 'Beta') for i in range(6)])
        ranking = [dict(player='Alpha', elo=950), dict(player='Beta', elo=1200)]
        self.assertIn('leads Beta 4–2', text(player_stories(archive, 'Alpha', ranking=ranking)))
        archive['matches'] = archive['matches'][:2]
        self.assertNotIn('lower current Elo', text(player_stories(archive, 'Alpha', ranking=ranking)))

    def test_comeback_and_perfect_bracket_need_known_scores(self):
        rows = [match(1, 0, 'Alpha', 'Beta', 'Beta', (0, 1), 'group_stage'),
                match(1, 1, 'Alpha', 'Gamma', 'Gamma', (0, 1), 'group_stage')]
        rows += [match(1, i + 2, 'Alpha', opponent, 'Alpha') for i, opponent in enumerate(('Beta', 'Gamma', 'Beta'))]
        archive = dict(events=[event(1)], appearances=[appearance(1, 'Alpha', 1)], matches=rows)
        result = text(tournament_stories(archive, 1))
        self.assertIn('opening 2 sets', result)
        self.assertIn('3 consecutive', result)
        self.assertIn('6–0', result)
        rows[-1]['score_known'] = False
        self.assertNotIn('without dropping', text(tournament_stories(archive, 1)))

    def test_debut_reports_field_tie_and_cautious_sample(self):
        archive = dict(events=[event(1, 'Beta')],
                       appearances=[appearance(1, 'Alpha', 3), appearance(1, 'Gamma', 3), appearance(1, 'Beta', 1)],
                       matches=[match(1, 0, 'Alpha', 'Gamma', 'Alpha'), match(1, 1, 'Alpha', 'Beta', 'Beta', (1, 2))])
        result = text(player_stories(archive, 'Alpha'))
        self.assertIn('joint #3 in a field of 3', result)
        self.assertIn('only an initial picture', result)
        self.assertIn('1–2 deciding-game loss', result)

    def test_last_result_qualifies_longer_upward_trend(self):
        archive = dict(events=[event(i, 'Beta') for i in range(1, 5)],
                       appearances=[appearance(i, 'Alpha', 4) for i in range(1, 5)], matches=[])
        timeline = [dict(elo_exact=x) for x in (1000, 1040, 1080, 1050)]
        result = text(player_stories(archive, 'Alpha', timeline=timeline))
        self.assertIn('gained 50.0', result)
        self.assertIn('30.0-point drop', result)

    def test_broken_streak_uses_ordered_prior_meetings(self):
        archive = dict(events=[event(1, 'Beta'), event(2)],
                       appearances=[appearance(1, 'Alpha', 2), appearance(2, 'Alpha', 1)],
                       matches=[match(1, i, 'Alpha', 'Beta', 'Beta') for i in range(4)] +
                       [match(2, 0, 'Alpha', 'Beta', 'Alpha')])
        self.assertIn('4-set losing streak', text(player_stories(archive, 'Alpha')))

    def test_group_upsets_are_contrasted_with_final_placement(self):
        archive = dict(events=[event(1, 'Beta')],
                       appearances=[appearance(1, 'Alpha', 4), appearance(1, 'Beta', 1),
                                    appearance(1, 'Gamma', 3)],
                       matches=[match(1, 0, 'Alpha', 'Beta', 'Alpha', (1, 0), 'group_stage'),
                                match(1, 1, 'Alpha', 'Gamma', 'Alpha', (1, 0), 'group_stage')])
        result = text(player_stories(archive, 'Alpha'))
        self.assertIn('both eventual podium finishers', result)
        self.assertIn('finished #4', result)

    def test_selection_is_stable_and_removes_duplicate_themes(self):
        stories = [Story(10, 'a', 'low'), Story(100, 'a', 'high'), Story(50, 'b', 'other')]
        self.assertEqual(select_stories(stories), ['high', 'other'])
        self.assertEqual(select_stories(list(reversed(stories))), ['high', 'other'])
        self.assertEqual(select_stories(stories, 0), [])

    def test_bo1_does_not_prove_sweep_or_close_series(self):
        meetings = [dict(score='1-0') for _ in range(8)]
        self.assertIsNone(_rivalry_scoreline_sentence(meetings))
        self.assertEqual(_count_close_sets([dict(score_known=True, player_1_score=1, player_2_score=0)]), 0)

    def test_native_bracket_final_is_recognized(self):
        final = dict(stage='bracket', winner='Alpha', round_label='Grand Final (GF)')
        self.assertEqual(_find_final_match([dict(stage='group_stage', winner='Beta'), final]), final)

    def test_enriched_profile_prioritizes_story_over_generic_stats(self):
        result = generate_player_summary(
            dict(player='Alpha', titles=2, appearances=6, decided_matches=30, current_elo=1200, winrate=60),
            dict(stories=[Story(100, 'placements', 'Alpha has reached five finals.')]), 2)
        self.assertTrue(result.startswith('Alpha has reached five finals.'))
        self.assertIn('two-time World Champion', result)
        self.assertIn('1200.0', result)

    def test_established_profile_keeps_career_context_with_one_story(self):
        result = generate_player_summary(
            dict(player='Alpha', titles=1, appearances=12, decided_matches=76,
                 current_elo=1030, peak_elo=1140, winrate=50),
            dict(stories=[Story(65, 'placements', 'Alpha is waiting for another title.')],
                 best_elo_event=dict(tournament='WC 07', elo_change=101)), 5)
        self.assertIn('12 tournament appearances', result)
        self.assertIn('biggest Elo gain', result)
        self.assertIn('1140.0', result)

    def test_titleless_veteran_keeps_best_finish(self):
        result = generate_player_summary(
            dict(player='Alpha', titles=0, appearances=9, decided_matches=49,
                 current_elo=755, peak_elo=1001, winrate=10, best_result=5),
            dict(stories=[Story(99, 'revenge', 'Alpha broke an opponent losing streak.')]), 8)
        self.assertIn('9 tournaments', result)
        self.assertIn('5th place', result)
        self.assertIn('career-high Elo', result)

    def test_debut_omits_premature_career_retrospective(self):
        result = generate_player_summary(
            dict(player='Alpha', titles=0, appearances=1, decided_matches=9,
                 current_elo=981, peak_elo=1010, winrate=33, best_result=5),
            dict(stories=[Story(110, 'debut', 'Alpha made a debut. One event offers only an initial picture.'),
                          Story(95, 'debut_run', 'The bracket ended in a deciding game.')]), 6)
        self.assertNotIn('career-high', result)
        self.assertNotIn('still chasing', result)
        self.assertLessEqual(len(result.split()), 65)

    def test_outlook_includes_story_and_latest_downturn(self):
        result = generate_tournament_preview(dict(
            ranking=[dict(player='Alpha', elo=1200, rank=1), dict(player='Beta', elo=1190, rank=2), dict(player='Gamma', elo=1100, rank=3)],
            recent_form=[dict(player='Beta', matches=10, wins=5, losses=5, winrate=50,
                              elo_change_last_three=40, elo_change_latest=-20)],
            stories=[Story(100, 'placements', 'Gamma has reached five consecutive finals.')]))
        self.assertIn('five consecutive finals', result)
        self.assertNotIn('chasing field', result)
