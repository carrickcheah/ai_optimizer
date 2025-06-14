# Lookback Period Comparison Test Results

## Test Overview
- **Test Date**: 2025-06-12 23:55:04
- **Planning Horizon**: 180 days (constant)
- **LCD Filter**: Tomorrow and future dates only
- **Test Periods**: 30, 60, 90, 120, 180, 270, 365 days lookback

## Results Summary

| Lookback Days | Total Jobs | Total Machines | Jobs with Processing Time | Subcon Jobs | Loading Time (s) |
|---------------|------------|----------------|---------------------------|-------------|------------------|
| 30 | 811 | 87 | 801 | 45 | 0.067 |
| 60 | 811 | 87 | 801 | 45 | 0.065 |
| 90 | 1019 | 90 | 1006 | 69 | 0.087 |
| 120 | 1019 | 90 | 1006 | 69 | 0.081 |
| 180 | 1019 | 90 | 1006 | 69 | 0.081 |
| 270 | 1019 | 90 | 1006 | 69 | 0.081 |
| 365 | 1019 | 90 | 1006 | 69 | 0.080 |

## Analysis

### Job Count Progression
- **30 days**: 811 jobs
- **60 days**: 811 jobs
- **90 days**: 1019 jobs
- **120 days**: 1019 jobs
- **180 days**: 1019 jobs
- **270 days**: 1019 jobs
- **365 days**: 1019 jobs

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
