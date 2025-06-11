6. cpsat_solver.py:639-649 - Search windows: 90, 180, 365 days
    - Issue: Fixed search windows waste computation
    - Impact: Major solver performance impact
  7. greedy_solver.py:366 - search_limit_hours = 8760
    - Issue: 1-year search limit for all jobs
    - Impact: Unnecessary computation for short-term jobs

  💾 DATA QUALITY MASKING:

  8. chart_generator.py:208-219 - Machine name fallback patterns
    - Issue: Hardcoded machine mappings hide real data issues
    - Impact: Masks database inconsistencies
  9. mariadb_parser.py:110 - max_jobs: int = 1500
    - Issue: Hard limit may prevent loading all necessary jobs
    - Impact: Incomplete scheduling
  10. urgent_handling.py:43 - reduction_factor = 0.5 (50%)
    - Issue: Fixed 50% time reduction for urgent jobs
    - Impact: May be too aggressive/conservative

  RECOMMENDATION:

  Should I proceed to fix these hardcoded values? The top priorities would be:

  1. Remove hardcoded job attributes (break_hours, no_prod, priority) - these are corrupting your real data
  2. Make performance parameters configurable (batch_size, search_windows)
  3. Move business thresholds to environment variables (buffer thresholds, utilization limits)

  These fixes will reveal real data quality issues and improve both performance and accuracy significantly.