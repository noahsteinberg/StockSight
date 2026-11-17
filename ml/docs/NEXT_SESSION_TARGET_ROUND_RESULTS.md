# Next-session continuous-target round

Training-period research only. Diagnostic probabilities are not deployable confidence.

| Configuration | Direction target | Accuracy | Balanced accuracy | AUC | Brier | Rank IC | Decile spread |
| --- | --- | --- | --- | --- | --- | --- | --- |
| absolute_return_hgb | absolute | 52.242% | 50.769% | 0.51097 | 0.250084 | 0.023212668172754396 | 0.0019246162019749518 |
| excess_return_hgb | relative | 50.844% | 50.664% | 0.51206 | 0.249835 | 0.025491019202201367 | 0.0020463939540252187 |
| combined_market_stock | absolute | 51.601% | 50.028% | 0.49582 | 0.249975 | 0.025491019202201367 | 0.0020463939540252187 |

Direction uses raw score > 0; Brier uses calibration-block-only logistic mapping.
Excess-return direction means outperform, not price up. Ranking uses realized absolute return, whose within-date ordering equals excess return.
Decile spread is gross/descriptive, not an executable trading return. All outcomes are unclipped.
No validation/final-test scoring, model export, or promotion. Review every fold and block interval before deciding next steps.
