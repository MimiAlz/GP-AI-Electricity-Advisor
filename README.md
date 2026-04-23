# GP-AI-Electricity-Advisor

# GP

Main Idea: 

Electricity in Jordan is expensive, and bills increase significantly after passing limits like 300 or 600 kWh. Most families don’t know which appliances consume the most power. This app helps families understand, predict, and reduce their electricity bills by showing their expected usage, appliance breakdowns, and personalized saving tips.

How It Works:

Input:

- Old electricity bills
- Basic family info (e.g. AC and heater usage hours, laundry frequency per week)
- Weather data (hot/cold weeks)
- Tariff rules in Jordan (the jump after 300 and 600 kWh)
- **Smart meter readings** (real half-hourly data, if available)

Process:

- Estimates power consumption per appliance (AC, heater, fridge, etc.)
- Shows if the family is close to exceeding a tariff limit
- Suggests changes (e.g. "Use the AC one hour less daily to save 10 JOD")
- Lets users simulate bill changes with sliders (AC hours, heater, laundry frequency, etc.)
- **Forecasts future bills using real smart meter data if available**

Output:

- Expected monthly bill
- Which appliances take the most power
- How close they are to the next billing tier
- Personalized saving tips

Key Features:

- Bill Forecasting: Predicts next month's electricity bill based on historical data, weather, and holidays. If smart meter data is available, uses real readings for more accurate forecasts (with backend pagination to fetch all data, even if >1000 rows).
- Scenario Simulator: Allows users to test "what if" changes and instantly see bill effects.
- Personalized Tips: Offers family-specific advice, like shifting laundry days or reducing AC usage, "Do laundry on the weekend" or "Use the AC one hour less each day", to save money.

Why It’s Helpful:

Makes energy use visible and understandable, helping families avoid higher tiers, save money, and reduce overall consumption. 



Some random ideas:

-create an automatic plan using CV (optional) using an electricity bill image dataset

-reccomendation for subsidy or non-subsidy tariff plan





