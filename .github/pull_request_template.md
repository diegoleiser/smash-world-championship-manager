## Summary

<!-- What changes and why. One task per pull request. -->

## Checklist

- [ ] Full test suite passes: `PYTHONPATH=src python -m unittest discover -s tests -v`
- [ ] New rules or fixed regressions have a test at the right level
- [ ] UI changes checked manually on desktop and mobile (light and dark)
- [ ] Compatibility facades (`tournament_manager`, `smash_statistics`, `narratives`) unchanged, or the API change was approved
- [ ] No schema, model or Elo rule change without explicit approval
- [ ] No private data in the diff: databases, seeds, Challonge raw data, overrides, model artifacts, credentials, session notes
- [ ] No unrelated cleanup or generated files

## Manual verification

<!-- Scenarios checked by hand, fixture or demo database used, checks deliberately skipped. -->
