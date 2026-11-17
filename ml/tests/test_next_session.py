import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

spec = importlib.util.spec_from_file_location('next_session', Path(__file__).parents[1]/'scripts/next-session.py')
n = importlib.util.module_from_spec(spec)
spec.loader.exec_module(n)


def prices():
    return pd.DataFrame({'ticker': ['A']*4+['B']*4,
                         'date': list(pd.to_datetime(['2018-12-21', '2018-12-24', '2018-12-26', '2018-12-27']))*2,
                         'adj_close': [100, 101, 101, 99, 10, 9, 8, 7], 'bad_bar': False})


def test_holiday_target_and_ties_and_stock_isolation():
    frame = n.labels(prices())
    a = frame[frame.ticker == 'A'].reset_index(drop=True)
    assert a.loc[1, 'target_date'] == pd.Timestamp('2018-12-26')
    assert np.isnan(a.loc[1, 'label'])
    assert a.loc[0, 'label'] == 1 and a.loc[2, 'label'] == 0
    assert np.isnan(a.loc[3, 'label'])
    assert frame[frame.ticker == 'B'].label.dropna().eq(0).all()


def test_missing_and_bad_bars_never_bridged():
    p = prices().drop(index=1)
    assert np.isnan(n.labels(p).iloc[0].label)
    p = prices()
    p.loc[1, 'bad_bar'] = True
    assert n.labels(p).iloc[:2].label.isna().all()


def test_future_prices_do_not_change_earlier_label():
    p = prices()
    old = n.labels(p).iloc[0].label
    p.loc[2:3, 'adj_close'] = 1000
    assert n.labels(p).iloc[0].label == old


def test_calibration_has_strict_target_boundary():
    dates = pd.bdate_range('2000-01-03', periods=800)
    rows = pd.DataFrame({'date': dates[:-1], 'target_date': dates[1:]})
    base, cal = n.partition(rows)
    assert cal.date.nunique() == 252
    assert base.target_date.max() < cal.date.min()


def test_baseline_neutral_is_majority():
    rows = pd.DataFrame({'rate': [.6, .4], 'previous_return': [0., 0.]})
    for key in ['momentum', 'reversal']:
        np.testing.assert_array_equal(n.references(rows)[key], [1, 0])


def test_calibration_is_fitted_separately():
    p = np.array([.1, .2, .8, .9])
    mapper = n.calibrate(p, [0, 0, 1, 1])
    q = n.calibrated(mapper, p)
    assert np.isfinite(q).all() and (np.diff(q) > 0).all()


def test_nonpositive_endpoint_is_invalid():
    p = prices()
    p.loc[1, 'adj_close'] = 0
    assert n.labels(p).iloc[:2].label.isna().all()


def test_adjusted_not_raw_split_close_is_target():
    p = prices()
    p['close'] = [100, 50, 51, 49, 10, 9, 8, 7]
    # Raw close halves, while adjusted series rises; adjustment defines the outcome.
    assert n.labels(p).iloc[0].label == 1


def test_date_block_contrasts_equal_identical_baseline():
    rows = pd.DataFrame({'date': pd.bdate_range('2010-01-04', periods=20).repeat(2),
                         'label': [0, 1]*20, 'p': [.4, .6]*20,
                         'rate': .5, 'previous_return': [-.01, .01]*20})
    result = n.uncertainty([rows], 'p', 10)
    assert result['momentum']['ci95'] == [0., 0.]
    assert result['reversal']['adjusted_lower'] == 1.
