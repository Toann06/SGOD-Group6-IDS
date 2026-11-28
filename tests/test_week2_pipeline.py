from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from src.c2_week2 import load_handoff_csv, run_pipeline, extract_features, map_labels

FIXTURE=Path(__file__).parents[1]/"data"/"b3_handoff"/"labeled_sample.csv"
MANIFEST=FIXTURE.parent/"manifest.json"


def test_fixture_load_preserves_hex_and_schema():
    df=load_handoff_csv(FIXTURE)
    assert len(df)==18
    assert df.loc[0,"can_id"]=="0130"
    assert df.loc[0,"data_2"]=="00"


def test_a2_frame18_order_shape_and_no_leakage():
    df=load_handoff_csv(FIXTURE)
    features,y,meta,ordered,names,label_spec=extract_features(df,"hcrl_frame_18")
    assert features.shape==(18,18)
    assert names[0:2]==["can_id_int","dlc"]
    assert names[2:10]==[f"data_{i}" for i in range(8)]
    assert names[10:]==[f"payload_mask_{i}" for i in range(8)]
    assert features.iloc[0]["can_id_int"]==0x130
    assert features.iloc[0]["data_2"]==0
    assert features.iloc[0]["payload_mask_2"]==1
    assert "label" not in features.columns and "attack_type" not in features.columns


def test_binary_output_contract_and_batch_last(tmp_path):
    report=run_pipeline(FIXTURE,tmp_path,batch_size=7,profile="hcrl_frame_18",label_mode="binary",manifest_path=MANIFEST)
    X=np.load(tmp_path/"X.npy"); y=np.load(tmp_path/"y.npy")
    assert X.shape==(18,18) and X.dtype==np.float32
    assert y.shape==(18,) and y.dtype==np.int64
    assert np.isfinite(X).all()
    assert report["n_batches"]==3
    assert [b["rows"] for b in report["batches"]]==[7,7,4]
    assert report["manifest_integrity"]["matches"] is True


def test_multiclass_mapping():
    df=load_handoff_csv(FIXTURE)
    y, spec=map_labels(df,"multiclass")
    assert set(y)=={0,1,2,3,4}
    assert y.dtype==np.int64
    assert spec["mapping"]=={"normal":0,"dos":1,"fuzzy":2,"gear":3,"rpm":4}


def test_temporal_baseline_a_profile_smoke(tmp_path):
    report=run_pipeline(FIXTURE,tmp_path,batch_size=8,profile="b2_baseline_a_23",label_mode="binary")
    X=np.load(tmp_path/"X.npy")
    assert X.shape==(18,23)
    assert X.dtype==np.float32 and np.isfinite(X).all()
    assert report["temporal_fixture_caveat"].startswith("B3 handoff is stratified")


def test_reject_bad_dlc():
    df=pd.read_csv(FIXTURE,dtype=str,keep_default_na=False)
    df.loc[0,"dlc"]="9"
    p=FIXTURE.parent/"bad_dlc_temp.csv"; df.to_csv(p,index=False)
    try:
        with pytest.raises(ValueError,match="Invalid DLC"):
            load_handoff_csv(p)
    finally:
        p.unlink(missing_ok=True)


def test_reject_missing_byte_within_dlc():
    df=pd.read_csv(FIXTURE,dtype=str,keep_default_na=False)
    df.loc[0,"data_0"]=""
    p=FIXTURE.parent/"bad_payload_temp.csv"; df.to_csv(p,index=False)
    try:
        with pytest.raises(ValueError,match="Missing payload byte"):
            load_handoff_csv(p)
    finally:
        p.unlink(missing_ok=True)


def test_reject_nonzero_padding_outside_dlc():
    df=pd.read_csv(FIXTURE,dtype=str,keep_default_na=False)
    df.loc[0,"dlc"]="2"
    for i in range(2,8): df.loc[0,f"data_{i}"]=""
    df.loc[0,"data_7"]="ff"
    p=FIXTURE.parent/"bad_padding_temp.csv"; df.to_csv(p,index=False)
    try:
        with pytest.raises(ValueError,match="beyond DLC"):
            load_handoff_csv(p)
    finally:
        p.unlink(missing_ok=True)


def test_csv_column_order_does_not_change_feature_order(tmp_path):
    df=pd.read_csv(FIXTURE,dtype=str,keep_default_na=False)
    shuffled=df[df.columns[::-1]]
    p=tmp_path/"shuffled.csv"; shuffled.to_csv(p,index=False)
    loaded=load_handoff_csv(p)
    features,_,_,_,names,_=extract_features(loaded,"hcrl_frame_18")
    assert names[0]=="can_id_int" and names[-1]=="payload_mask_7"
    assert features.iloc[0]["can_id_int"]==0x130
