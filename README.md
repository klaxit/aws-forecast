# aws-forecast

## Credits

Forked from its [original repository](https://github.com/klaxit/aws-forecast), simplified and adapted to [@Klaxit](https://github.com/klaxit) needs. Many thanks to [@jimzucker](https://github.com/jimzucker) for sharing this!

## User Story
I found myself logging in daily check our AWS spend and change to prior month to keep an eye on our AWS bill and decided to create a script to slack it one time per day to save time.

So I set out to automate this as a slack post daily to save time.  While doing this I found that Forecast with % change from prior month that we see at the top of Cost Explorer are not directly available from the Cost Explorer API. Also, Current month costs is not accurate if AWS Saving Plans are used (as it includes that total amount of the reserved capacity from day one).

![Image of Cost Explorer](https://github.com/klaxit/aws-forecast/blob/main/images/cost_explorer.png)



## Solution
### AWS Architecture
![AWS Architecture](https://github.com/klaxit/aws-forecast/blob/main/images/aws_architecture.jpg)

### Setup
See these instructions: [Click here](https://github.com/klaxit/aws-forecast/blob/main/MANUAL_SETUP_README.md)

### Environment Variables
See documentation at the top of `get_forecast.py`.
### Sample Output
![Sample Output of get_forecast](https://github.com/klaxit/aws-forecast/blob/main/images/get_forecast_sample_output.png)

### Command line (for development/testing)
```python3 get_forecast.py```
### Technical Notes
#### AWS API Used
1. get_cost_forecast - used to get current month forecast. (note we exclude credits)
2. get_cost_and_usage - used to get prior & current month actuals (note we exclude credits)

#### Boundary conditions handled
In testing I found several situations where the calls to get_cost_forecast would fail that we address in function calc_forecast:
1. Weekends - there is a sensitivity to the start date being on a weekend
2. Failure on new accounts or start of the month - on some days the calc fails due to insufficient data and we have to fall back to actuals
