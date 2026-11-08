# Fitbit MCP server (Google Health API)

A remote MCP server for Claude.ai custom connectors. It reads and logs Fitbit data through the
[Google Health API](https://developers.google.com/health), which replaced the Fitbit Web API
([migration guide](https://developers.google.com/health/migration)).

## How it works

- MCP endpoint (Streamable HTTP): `https://fitbit-mcp.fly.dev/<MCP_PATH_SECRET>/mcp`. Any other path returns 404.
- Google sign-in: open `https://fitbit-mcp.fly.dev/auth/start?key=<MCP_PATH_SECRET>`. Google redirects to
  `/auth/callback`. The refresh token is stored on the Fly volume at `/data/google_token.json`.
- If the token is missing or expired, every tool returns a short message with the sign-in link.
- Rollup requests are split to respect the API's range limits (14 days for heart-rate, active-minutes,
  total-calories, calories-in-heart-rate-zone; 90 days for all other types). List results are paginated.

## Deployment

Pushing to `master` runs `.github/workflows/deploy.yml`, which runs the tests, creates the Fly app and the
`fitbit_data` volume if needed, pushes secrets to Fly, and deploys.

Required GitHub Actions secrets: `FLY_API_TOKEN`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `MCP_PATH_SECRET`.

Google Cloud OAuth client: type "Web application", redirect URI `https://fitbit-mcp.fly.dev/auth/callback`.
Scopes used (see `src/fitbit_mcp/config.py`):
`activity_and_fitness.readonly`, `health_metrics_and_measurements.readonly`,
`health_metrics_and_measurements.writeonly`, `sleep.readonly`, `nutrition.readonly`, `nutrition.writeonly`,
`profile.readonly`, `settings.readonly`.

## Tools

get_profile, get_devices, get_daily_activity_summary, get_activity_timeseries_by_range, get_activity_intraday,
get_azm_by_range, get_activity_log_list, get_heart_rate_by_range, get_heart_rate_intraday, get_hrv_by_date,
get_hrv_by_range, get_sleep_by_date, get_sleep_by_date_range, get_spo2_by_range, get_breathing_rate_by_range,
get_skin_temperature_by_range, get_cardio_score_by_range, get_weight_log, get_body_timeseries_by_range,
get_food_log, get_water_log, log_food, log_water, log_weight, delete_food_log.

Not included: `search_foods`. The API's `food` data type supports only list and get, with no search
parameter ([nutrition guide](https://developers.google.com/health/data-types/nutrition)). `log_food` writes an
"anonymous food" entry with the calories and nutrients you supply. BMI is not a Google Health data type.

## Tests

```
pip install . pytest
pytest -q tests
```

Based on [npab19/fitbit-mcp](https://github.com/npab19/fitbit-mcp) (MIT). Field mappings cross-checked against
[Ring8688/google-health-worker-mcp-V1](https://github.com/Ring8688/google-health-worker-mcp-V1) (MIT).
