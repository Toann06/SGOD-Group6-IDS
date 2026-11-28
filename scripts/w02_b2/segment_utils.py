"""Gap-aware boundaries for ordered parsed CAN observations."""
import pandas as pd

GAP_SECONDS = 1.0

def segment_context(df, gap_seconds=GAP_SECONDS):
    """Return local segment IDs, contiguous boundary keys and valid global IAT.

    Input must be in observation order within each source/split. Explicit IDs
    are respected; inferred IDs are local to the supplied batch, not global.
    """
    ts = pd.to_numeric(df["timestamp"], errors="raise").reset_index(drop=True)
    source = df.get("source_file", pd.Series("unknown", index=df.index)).reset_index(drop=True)
    split = df.get("split", pd.Series("unknown", index=df.index)).reset_index(drop=True)
    explicit = df.get("segment_id")
    delta = ts.diff()
    source_change = source.ne(source.shift())
    gap = delta.gt(gap_seconds) | delta.lt(0) | delta.isna()
    # Local IDs count gaps within contiguous source runs.
    local = (gap & ~source_change).groupby(source_change.cumsum()).cumsum().astype(int)
    if explicit is not None:
        local = explicit.reset_index(drop=True)
        if local.isna().any():
            raise ValueError("Missing segment_id")
    boundary = source_change | split.ne(split.shift()) | gap | local.ne(local.shift())
    key = boundary.cumsum().astype(str)
    iat = delta.mask(boundary)
    return tuple(pd.Series(x.to_numpy(), index=df.index) for x in (local, key, iat))
