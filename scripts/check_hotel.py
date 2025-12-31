#!/usr/bin/env python3
"""Check recommended_hotel in itinerary"""
import json

with open('/tmp/canada_itinerary.json') as f:
    data = json.load(f)

ai = data.get('ai_generated_itinerary', {})
daily_plans = ai.get('daily_plans', [])

print('=' * 70)
print('CANADA TRIP - RECOMMENDED_HOTEL CHECK')
print('=' * 70)

print(f'\nTitle: {data.get("title", "N/A")}')
print(f'Daily Plans: {len(daily_plans)}')

for i, day in enumerate(daily_plans, 1):
    print(f'\n{"="*70}')
    print(f'📅 Day {i}: {day.get("title", "N/A")}')
    print(f'   Location: {day.get("location_city", "N/A")}, {day.get("location_country", "N/A")}')
    print(f'   Is Travel Day: {day.get("is_travel_day", False)}')
    if day.get("travel_from") or day.get("travel_to"):
        print(f'   Travel: {day.get("travel_from", "N/A")} → {day.get("travel_to", "N/A")}')
    
    # Check recommended_hotel
    rec_hotel = day.get('recommended_hotel')
    if rec_hotel:
        print(f'\n   🏨 RECOMMENDED HOTEL:')
        if isinstance(rec_hotel, dict):
            print(f'      Name: {rec_hotel.get("title", rec_hotel.get("name", "N/A"))}')
            print(f'      Price: {rec_hotel.get("price_per_night", rec_hotel.get("price", "N/A"))}')
            url = rec_hotel.get("affiliate_url", rec_hotel.get("booking_url", ""))
            if url:
                print(f'      URL: {url[:60]}...')
        else:
            print(f'      Value: {rec_hotel}')
    else:
        print(f'\n   🏨 RECOMMENDED HOTEL: ❌ None')
    
    # Check recommended_flights
    rec_flights = day.get('recommended_flights', [])
    if rec_flights:
        print(f'\n   ✈️  RECOMMENDED FLIGHTS: {len(rec_flights)} options')
    else:
        print(f'\n   ✈️  RECOMMENDED FLIGHTS: ❌ None')
    
    # Daily tips
    tips = day.get('daily_tips', [])
    if tips:
        print(f'\n   💡 DAILY TIPS: {len(tips)}')
        for t in tips[:2]:
            print(f'      - {t[:60]}...')

# Global hotel options
print(f'\n{"="*70}')
print('GLOBAL HOTEL OPTIONS')
print('=' * 70)
hotels = ai.get('hotel_options', [])
print(f'Total: {len(hotels)}')
for h in hotels[:3]:
    name = h.get('title', h.get('name', 'N/A'))
    price = h.get('price_per_night', h.get('price', 'N/A'))
    url = h.get('affiliate_url', h.get('booking_url', 'N/A'))
    print(f'  - {name}: {price}')
    if url and url != 'N/A':
        print(f'    URL: {url[:60]}...')

# Summary
print(f'\n{"="*70}')
print('SUMMARY')
print('=' * 70)
has_rec_hotel = sum(1 for d in daily_plans if d.get('recommended_hotel'))
has_rec_flights = sum(1 for d in daily_plans if d.get('recommended_flights'))
has_tips = sum(1 for d in daily_plans if d.get('daily_tips'))

print(f'Days with recommended_hotel: {has_rec_hotel}/{len(daily_plans)}')
print(f'Days with recommended_flights: {has_rec_flights}/{len(daily_plans)}')
print(f'Days with daily_tips: {has_tips}/{len(daily_plans)}')
print(f'Global hotel_options: {len(hotels)}')
