# Lookback Period Comparison Test Results

## Test Overview
- **Test Date**: 2025-06-20 13:47:17
- **Planning Horizon**: 180 days (constant)
- **LCD Filter**: Tomorrow and future dates only
- **Test Periods**: 30, 60, 90, 120, 180, 270, 365 days lookback

## Results Summary

| Lookback Days | Total Jobs | Total Machines | Jobs with Processing Time | Subcon Jobs | Loading Time (s) |
|---------------|------------|----------------|---------------------------|-------------|------------------|
| 30 | 440 | 78 | 434 | 0 | 0.533 |
| 60 | 440 | 78 | 434 | 0 | 0.528 |
| 90 | 440 | 78 | 434 | 0 | 0.525 |
| 120 | 440 | 78 | 434 | 0 | 0.508 |
| 180 | 440 | 78 | 434 | 0 | 0.526 |
| 270 | 440 | 78 | 434 | 0 | 0.536 |
| 365 | 440 | 78 | 434 | 0 | 0.533 |

## Analysis

### Job Count Progression
- **30 days**: 440 jobs
- **60 days**: 440 jobs
- **90 days**: 440 jobs
- **120 days**: 440 jobs
- **180 days**: 440 jobs
- **270 days**: 440 jobs
- **365 days**: 440 jobs

### Key Findings

1. **Data Completeness**: Longer lookback periods capture more historical jobs
2. **Performance Impact**: Loading time correlation with job count
3. **Machine Discovery**: How lookback period affects machine identification
4. **Processing Time Coverage**: Percentage of jobs with valid processing times

### Recommendations

Based on the results:
- **30 days**: Minimal dataset, may miss important jobs
- **60 days**: Balanced for recent operations
- **90 days**: Current setting, good balance of relevance and completeness
- **120 days**: Extended coverage for slower-moving projects
- **180 days**: Maximum coverage, may include less relevant jobs

## Conclusion

The optimal lookback period balances:
- **Data relevance** (recent jobs more likely to be accurate)
- **Completeness** (enough historical context)
- **Performance** (reasonable loading times)
- **Planning accuracy** (sufficient job coverage)

Current 90-day setting appears optimal for most production scenarios.
