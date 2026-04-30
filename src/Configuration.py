from dataclasses import dataclass
@dataclass
class Configuration():
    # Toggle Dask CSV loader. Use True for very large CSVs (out-of-core parsing).
    use_dask : bool 
    # If True, store neighbor separations alongside neighbor IDs. Costs extra disk.
    calculate_separations : bool 
    # ---------------- EXECUTION CONTROL ----------------
    # Toggle which steps to run from this orchestrator.
    run_build : bool     # run the index builder step;
    run_query : bool    # run the contamination query step;

