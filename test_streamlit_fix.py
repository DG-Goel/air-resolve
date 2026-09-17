"""Quick test to verify Streamlit scenario loading works."""

from ui.helpers import load_scenario_data

scenarios = load_scenario_data()

print("✅ Scenario data loaded successfully\n")
print("Available scenarios:")
for key, scenario in scenarios.items():
    print(f"\n{key.upper()}:")
    print(f"  Name: {scenario['name']}")
    print(f"  Booking: {scenario['booking_reference']}")
    print(f"  Flight: {scenario['flight']}")
    print(f"  Status: {scenario['status']}")
    print(f"  Message length: {len(scenario['initial_message'])} chars")

print("\n✅ All scenario data is valid")
print("\nNow run: streamlit run app.py")
print("\nSteps to test:")
print("1. Click a scenario button (Priya/Arvind/Meher)")
print("2. Verify the message appears in the text box")
print("3. Click 'REVIEW & RESOLVE'")
print("4. Check the right panel for results")
