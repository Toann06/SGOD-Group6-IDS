import numpy as np
import pandas as pd
import pytest
from scripts.w02_b2.feature_extraction import extract_temporal_features, get_feature_names
from scripts.w02_b2.preprocessing_demo import PreprocessingPipeline

@pytest.fixture
def frames():
    return pd.DataFrame({'timestamp':[0., .1, .2, 2., 2.2, 2.4], 'source_file':['a']*6, 'can_id':['001']*6, 'dlc':[2]*6, **{f'data_{i}':['01' if i<2 else None]*6 for i in range(8)}})

def test_gap_resets_all_temporal(frames):
    out=extract_temporal_features(frames)
    assert out.loc[3,['global_iat','inter_arrival_time','rolling_mean_iat','rolling_std_iat']].isna().all()
    assert out.loc[3,'can_id_freq_1s']==1
    assert out.loc[4,'rolling_mean_iat']==pytest.approx(.2)

def test_explicit_segment_resets_frequency(frames):
    frames['timestamp']=np.arange(6)*.1
    frames['segment_id']=[0,0,0,1,1,1]
    out=extract_temporal_features(frames)
    assert out.loc[3,'can_id_freq_1s']==1
    assert pd.isna(out.loc[3,'inter_arrival_time'])

def test_scaler_excludes_gap(frames):
    p=PreprocessingPipeline().fit(frames)
    assert p.get_fit_metadata()['iat_sample_count']==4
    assert p.get_fit_metadata()['iat_mean']==pytest.approx(.15)
    out=p.transform(frames)
    assert out.segment_id.tolist()==[0,0,0,1,1,1]
    assert pd.isna(out.loc[3,'iat_scaled'])

def test_source_and_split_reset(frames):
    frames['timestamp']=np.arange(6)*.1
    frames['source_file']=['a','a','b','b','b','b']
    frames['split']=['train','train','train','train','val','val']
    out=extract_temporal_features(frames)
    assert out.loc[[0,2,4],'global_iat'].isna().all()
    assert out.loc[[0,2,4],'can_id_freq_1s'].eq(1).all()
    with pytest.raises(ValueError): PreprocessingPipeline().fit(frames)

def test_segment_metadata_not_features():
    for variant,n in [('with_id',23),('without_id',22)]:
        names=get_feature_names(variant)
        assert len(names)==n
        assert 'segment_id' not in names and 'label_provenance' not in names
