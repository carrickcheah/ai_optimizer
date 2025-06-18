# Resource Chart Default Timeframe Update

## Change Made
- Updated resource chart component to default to 7-day timeframe instead of 'all'
- Changed `useState<string>('all')` to `useState<string>('7d')` in resource_chart.tsx:27

## File Modified
- `/Users/carrickcheah/Project/ai_optimizer/frontend/src/components/resource_chart.tsx`

## Impact
- Resource chart will now load with 7-day view by default
- Users can still change to other timeframes (1d, 14d, 1m, 3m, all) via dropdown
- Improves initial load performance and user experience by showing focused timeframe