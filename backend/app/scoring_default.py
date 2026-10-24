"""Default Recommendations Engine for IntelliOps.
Provides an extensible catalogue of 31+ location categories and a transparent,
explainable MCDA scoring methodology for business location recommendations.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple
from .schemas import (
    BusinessProfile, AnalysisMetadata, AnalysisResponse
)

DEFAULT_LOCATION_CATEGORIES = [
    {
        "id": "commercial_streets",
        "name": "Market Roads & Commercial Streets",
        "environment": "Commercial & Retail",
        "description": "High-density retail corridors with continuous pedestrian footfall, spontaneous shoppers, and strong commercial activity.",
        "footfall_level": 88.0,
        "accessibility_level": 82.0,
        "competition_density": 80.0,
        "typical_cost_tier": "Premium",
        "typical_monthly_cost": 45000,
        "parking_support": "Moderate",
        "primary_customer_segments": ["Shoppers", "Families", "Local residents", "Passersby"],
        "business_affinities": {
            "Restaurant": 88, "Cafe": 86, "Grocery Store": 84, "Clothing Store": 94,
            "Pharmacy": 80, "Bakery": 85, "Gym": 65, "Electronics Store": 92,
            "Salon": 82, "Stationery Store": 80, "General Retail": 92, "Other": 75
        }
    },
    {
        "id": "college_roads",
        "name": "College Roads & Educational Institution Areas",
        "environment": "Education & Student",
        "description": "Dynamic clusters surrounding universities, colleges, and schools characterized by high youth density and routine foot traffic.",
        "footfall_level": 90.0,
        "accessibility_level": 85.0,
        "competition_density": 65.0,
        "typical_cost_tier": "Moderate",
        "typical_monthly_cost": 30000,
        "parking_support": "Moderate",
        "primary_customer_segments": ["Students", "Faculty", "Young adults", "Commuters"],
        "business_affinities": {
            "Restaurant": 85, "Cafe": 96, "Grocery Store": 70, "Clothing Store": 82,
            "Pharmacy": 75, "Bakery": 88, "Gym": 85, "Electronics Store": 80,
            "Salon": 78, "Stationery Store": 98, "Bookstore": 95, "Co-working": 86, "Other": 72
        }
    },
    {
        "id": "bus_stands",
        "name": "Bus Stands & Regional Bus Terminals",
        "environment": "Transit & Transport",
        "description": "High-velocity transit nodes with constant daily passenger flow, commuters, and high turnover impulse-purchasing traffic.",
        "footfall_level": 95.0,
        "accessibility_level": 95.0,
        "competition_density": 75.0,
        "typical_cost_tier": "Moderate",
        "typical_monthly_cost": 35000,
        "parking_support": "Low",
        "primary_customer_segments": ["Commuters", "Travelers", "Daily workers", "Local shoppers"],
        "business_affinities": {
            "Restaurant": 82, "Cafe": 84, "Grocery Store": 80, "Clothing Store": 65,
            "Pharmacy": 88, "Bakery": 90, "Gym": 40, "Electronics Store": 70,
            "Salon": 60, "Stationery Store": 84, "Newsstand / Kiosk": 95, "Other": 68
        }
    },
    {
        "id": "railway_stations",
        "name": "Railway Stations & Station Surroundings",
        "environment": "Transit & Transport",
        "description": "24/7 travel hubs with vast commuter volume, luggage-friendly transit access, and strong demand for convenience goods and quick service.",
        "footfall_level": 96.0,
        "accessibility_level": 94.0,
        "competition_density": 78.0,
        "typical_cost_tier": "Premium",
        "typical_monthly_cost": 48000,
        "parking_support": "Moderate",
        "primary_customer_segments": ["Intercity travelers", "Daily commuters", "Tourists", "Logistics couriers"],
        "business_affinities": {
            "Restaurant": 84, "Cafe": 86, "Grocery Store": 82, "Clothing Store": 68,
            "Pharmacy": 92, "Bakery": 90, "Gym": 42, "Electronics Store": 72,
            "Salon": 62, "Stationery Store": 80, "Hotel / Hospitality": 90, "Other": 70
        }
    },
    {
        "id": "shopping_malls",
        "name": "Shopping Malls & Commercial Retail Centres",
        "environment": "Commercial & Retail",
        "description": "Managed retail spaces with structured amenities, dedicated parking, air-conditioned footfall, and high leisure spending.",
        "footfall_level": 90.0,
        "accessibility_level": 88.0,
        "competition_density": 85.0,
        "typical_cost_tier": "Premium",
        "typical_monthly_cost": 75000,
        "parking_support": "High",
        "primary_customer_segments": ["Leisure shoppers", "Families", "Youth", "Affluent consumers"],
        "business_affinities": {
            "Restaurant": 92, "Cafe": 90, "Grocery Store": 82, "Clothing Store": 96,
            "Pharmacy": 76, "Bakery": 86, "Gym": 88, "Electronics Store": 95,
            "Salon": 90, "Stationery Store": 72, "Entertainment / Cinema": 98, "Other": 75
        }
    },
    {
        "id": "local_markets",
        "name": "Local Markets & Wholesale Bazaars",
        "environment": "Commercial & Retail",
        "description": "Traditional commerce hubs with concentrated footfall, price-conscious consumers, bulk buying, and high transaction volume.",
        "footfall_level": 92.0,
        "accessibility_level": 75.0,
        "competition_density": 88.0,
        "typical_cost_tier": "Moderate",
        "typical_monthly_cost": 32000,
        "parking_support": "Low",
        "primary_customer_segments": ["Household buyers", "B2B traders", "Local residents", "Bargain hunters"],
        "business_affinities": {
            "Restaurant": 75, "Cafe": 68, "Grocery Store": 96, "Clothing Store": 85,
            "Pharmacy": 82, "Bakery": 80, "Gym": 45, "Electronics Store": 82,
            "Salon": 65, "Stationery Store": 88, "Wholesale Trade": 98, "Other": 70
        }
    },
    {
        "id": "main_roads",
        "name": "Main Roads & High-Traffic Arterial Streets",
        "environment": "Commercial & Retail",
        "description": "High-visibility vehicular and pedestrian corridors with prominent storefront branding and broad suburban connectivity.",
        "footfall_level": 86.0,
        "accessibility_level": 90.0,
        "competition_density": 70.0,
        "typical_cost_tier": "Moderate",
        "typical_monthly_cost": 38000,
        "parking_support": "Moderate",
        "primary_customer_segments": ["Vehicular commuters", "Neighborhood residents", "Destination shoppers"],
        "business_affinities": {
            "Restaurant": 85, "Cafe": 84, "Grocery Store": 86, "Clothing Store": 84,
            "Pharmacy": 90, "Bakery": 84, "Gym": 80, "Electronics Store": 88,
            "Salon": 80, "Stationery Store": 78, "Automobile Service": 90, "Other": 76
        }
    },
    {
        "id": "residential_neighbourhoods",
        "name": "Residential Neighbourhoods & Housing Colonies",
        "environment": "Healthcare & Community",
        "description": "Community-centric residential catchments characterized by repeat local clientele, convenience shopping, and long-term loyalty.",
        "footfall_level": 65.0,
        "accessibility_level": 78.0,
        "competition_density": 50.0,
        "typical_cost_tier": "Budget",
        "typical_monthly_cost": 22000,
        "parking_support": "Moderate",
        "primary_customer_segments": ["Families", "Senior citizens", "Children", "Local homeowners"],
        "business_affinities": {
            "Restaurant": 70, "Cafe": 78, "Grocery Store": 98, "Clothing Store": 60,
            "Pharmacy": 96, "Bakery": 92, "Gym": 82, "Electronics Store": 62,
            "Salon": 90, "Stationery Store": 85, "Daycare / Tutoring": 94, "Other": 72
        }
    },
    {
        "id": "commercial_business_districts",
        "name": "Commercial Business Districts (CBD)",
        "environment": "Office & Corporate",
        "description": "Prime downtown corporate and commercial centers featuring high-value enterprise offices, banks, and executive customer flow.",
        "footfall_level": 84.0,
        "accessibility_level": 92.0,
        "competition_density": 76.0,
        "typical_cost_tier": "Premium",
        "typical_monthly_cost": 65000,
        "parking_support": "High",
        "primary_customer_segments": ["Corporate executives", "Office professionals", "Business visitors", "Affluent clients"],
        "business_affinities": {
            "Restaurant": 90, "Cafe": 95, "Grocery Store": 65, "Clothing Store": 85,
            "Pharmacy": 78, "Bakery": 84, "Gym": 90, "Electronics Store": 82,
            "Salon": 85, "Stationery Store": 88, "Financial Advisory": 96, "Other": 78
        }
    },
    {
        "id": "office_parks_it_corridors",
        "name": "Office Areas & IT Parks Corridors",
        "environment": "Office & Corporate",
        "description": "Concentrated tech parks and multi-tenant office complexes with high daytime professional density and consistent weekday spend.",
        "footfall_level": 86.0,
        "accessibility_level": 88.0,
        "competition_density": 68.0,
        "typical_cost_tier": "Premium",
        "typical_monthly_cost": 55000,
        "parking_support": "High",
        "primary_customer_segments": ["Software professionals", "Corporate employees", "Contractors", "Young workers"],
        "business_affinities": {
            "Restaurant": 92, "Cafe": 98, "Grocery Store": 72, "Clothing Store": 74,
            "Pharmacy": 82, "Bakery": 86, "Gym": 94, "Electronics Store": 85,
            "Salon": 86, "Stationery Store": 86, "Co-working": 96, "Other": 77
        }
    },
    {
        "id": "industrial_manufacturing_zones",
        "name": "Industrial Areas & Manufacturing Zones",
        "environment": "Industrial & Logistics",
        "description": "Heavy and light production corridors offering wide access roads, high power availability, and low per-sqm rental rates.",
        "footfall_level": 48.0,
        "accessibility_level": 74.0,
        "competition_density": 35.0,
        "typical_cost_tier": "Industrial",
        "typical_monthly_cost": 28000,
        "parking_support": "High",
        "primary_customer_segments": ["Industrial workers", "Truck drivers", "Technicians", "B2B suppliers"],
        "business_affinities": {
            "Restaurant": 62, "Cafe": 50, "Grocery Store": 58, "Clothing Store": 40,
            "Pharmacy": 72, "Bakery": 60, "Gym": 55, "Electronics Store": 58,
            "Salon": 45, "Stationery Store": 50, "Hardware / Engineering": 98, "Warehouse": 96, "Other": 55
        }
    },
    {
        "id": "hospital_healthcare_zones",
        "name": "Hospital & Healthcare Districts",
        "environment": "Healthcare & Community",
        "description": "Medical hubs surrounding hospitals, clinics, and diagnostic labs with urgent, continuous health-oriented traffic.",
        "footfall_level": 85.0,
        "accessibility_level": 86.0,
        "competition_density": 65.0,
        "typical_cost_tier": "Moderate",
        "typical_monthly_cost": 36000,
        "parking_support": "Moderate",
        "primary_customer_segments": ["Patients", "Medical professionals", "Caregivers", "Visitors"],
        "business_affinities": {
            "Restaurant": 76, "Cafe": 82, "Grocery Store": 78, "Clothing Store": 45,
            "Pharmacy": 99, "Bakery": 80, "Gym": 52, "Electronics Store": 55,
            "Salon": 55, "Stationery Store": 72, "Diagnostic / Medical Equipment": 98, "Other": 68
        }
    },
    {
        "id": "tourist_destinations",
        "name": "Tourist Destinations & Sightseeing Areas",
        "environment": "Leisure & Hospitality",
        "description": "Heritage sites, scenic waterfronts, and cultural landmarks attracting regional, domestic, and international visitors.",
        "footfall_level": 92.0,
        "accessibility_level": 80.0,
        "competition_density": 82.0,
        "typical_cost_tier": "Premium",
        "typical_monthly_cost": 50000,
        "parking_support": "Moderate",
        "primary_customer_segments": ["Tourists", "Vacationers", "Weekend visitors", "Photographers"],
        "business_affinities": {
            "Restaurant": 95, "Cafe": 92, "Grocery Store": 65, "Clothing Store": 88,
            "Pharmacy": 75, "Bakery": 84, "Gym": 40, "Electronics Store": 65,
            "Salon": 68, "Stationery Store": 62, "Souvenir & Handicrafts": 98, "Other": 72
        }
    },
    {
        "id": "hospitality_hotel_districts",
        "name": "Hotels & Hospitality Districts",
        "environment": "Leisure & Hospitality",
        "description": "Accommodation corridors hosting business hotels, resorts, and travel lodgings with high-disposable-income guests.",
        "footfall_level": 80.0,
        "accessibility_level": 88.0,
        "competition_density": 65.0,
        "typical_cost_tier": "Premium",
        "typical_monthly_cost": 58000,
        "parking_support": "High",
        "primary_customer_segments": ["Hotel guests", "Conference delegates", "Business travelers", "Tourists"],
        "business_affinities": {
            "Restaurant": 94, "Cafe": 92, "Grocery Store": 68, "Clothing Store": 80,
            "Pharmacy": 82, "Bakery": 86, "Gym": 84, "Electronics Store": 74,
            "Salon": 88, "Stationery Store": 65, "Travel Concierge / Car Rental": 92, "Other": 74
        }
    },
    {
        "id": "food_streets_dining_clusters",
        "name": "Restaurants, Food Streets & Dining Clusters",
        "environment": "Commercial & Retail",
        "description": "Culinary epicenters benefiting from natural dining aggregation, late-night traffic, and social dining rituals.",
        "footfall_level": 94.0,
        "accessibility_level": 84.0,
        "competition_density": 86.0,
        "typical_cost_tier": "Moderate",
        "typical_monthly_cost": 42000,
        "parking_support": "Moderate",
        "primary_customer_segments": ["Foodies", "Youth", "Couples", "Dining groups", "Evening crowds"],
        "business_affinities": {
            "Restaurant": 99, "Cafe": 96, "Grocery Store": 60, "Clothing Store": 55,
            "Pharmacy": 65, "Bakery": 94, "Gym": 45, "Electronics Store": 45,
            "Salon": 58, "Stationery Store": 48, "Beverages / Desserts": 98, "Other": 65
        }
    },
    {
        "id": "supermarkets_grocery_markets",
        "name": "Supermarkets & Daily Grocery Market Hubs",
        "environment": "Commercial & Retail",
        "description": "High-frequency essential shopping clusters with steady weekday and surging weekend basket spends.",
        "footfall_level": 85.0,
        "accessibility_level": 84.0,
        "competition_density": 72.0,
        "typical_cost_tier": "Moderate",
        "typical_monthly_cost": 34000,
        "parking_support": "High",
        "primary_customer_segments": ["Household homemakers", "Working parents", "Local residents", "Bulk buyers"],
        "business_affinities": {
            "Restaurant": 75, "Cafe": 74, "Grocery Store": 98, "Clothing Store": 72,
            "Pharmacy": 90, "Bakery": 92, "Gym": 75, "Electronics Store": 78,
            "Salon": 78, "Stationery Store": 82, "Household Goods": 95, "Other": 72
        }
    },
    {
        "id": "retail_shopping_streets",
        "name": "Retail Fashion & Shopping Streets",
        "environment": "Commercial & Retail",
        "description": "Pedestrianized or semi-pedestrian shopping arcades with prominent shop fronts, window shoppers, and apparel buyers.",
        "footfall_level": 89.0,
        "accessibility_level": 82.0,
        "competition_density": 84.0,
        "typical_cost_tier": "Premium",
        "typical_monthly_cost": 48000,
        "parking_support": "Moderate",
        "primary_customer_segments": ["Fashion shoppers", "Youth", "Wedding buyers", "Boutique clients"],
        "business_affinities": {
            "Restaurant": 82, "Cafe": 88, "Grocery Store": 62, "Clothing Store": 99,
            "Pharmacy": 70, "Bakery": 80, "Gym": 68, "Electronics Store": 88,
            "Salon": 92, "Stationery Store": 75, "Jewelry / Accessories": 96, "Other": 74
        }
    },
    {
        "id": "transport_logistics_hubs",
        "name": "Transport Hubs & Freight Logistics Corridors",
        "environment": "Industrial & Logistics",
        "description": "Intermodal transport nodes connecting highways, rail freight, and distribution centers for frictionless logistics.",
        "footfall_level": 55.0,
        "accessibility_level": 92.0,
        "competition_density": 40.0,
        "typical_cost_tier": "Industrial",
        "typical_monthly_cost": 30000,
        "parking_support": "High",
        "primary_customer_segments": ["Fleet operators", "Logistics managers", "Truck drivers", "Wholesalers"],
        "business_affinities": {
            "Restaurant": 65, "Cafe": 55, "Grocery Store": 58, "Clothing Store": 35,
            "Pharmacy": 68, "Bakery": 60, "Gym": 40, "Electronics Store": 50,
            "Salon": 38, "Stationery Store": 55, "Warehouse": 98, "Courier / Logistics": 99, "Other": 55
        }
    },
    {
        "id": "warehousing_distribution_zones",
        "name": "Warehousing & Strategic Distribution Zones",
        "environment": "Industrial & Logistics",
        "description": "Large-span storage parks optimized for supply chain staging, pallet storage, and e-commerce fulfillment.",
        "footfall_level": 38.0,
        "accessibility_level": 88.0,
        "competition_density": 32.0,
        "typical_cost_tier": "Industrial",
        "typical_monthly_cost": 25000,
        "parking_support": "High",
        "primary_customer_segments": ["Supply chain directors", "B2B suppliers", "Distributors", "E-commerce ops"],
        "business_affinities": {
            "Restaurant": 45, "Cafe": 40, "Grocery Store": 42, "Clothing Store": 25,
            "Pharmacy": 50, "Bakery": 40, "Gym": 35, "Electronics Store": 45,
            "Salon": 30, "Stationery Store": 45, "Warehouse": 99, "Fulfillment Center": 99, "Other": 45
        }
    },
    {
        "id": "agricultural_markets",
        "name": "Agricultural Wholesale Markets (Mandis)",
        "environment": "Industrial & Logistics",
        "description": "Commodity exchanges and produce markets with massive early morning trade volume and regional farmer traffic.",
        "footfall_level": 82.0,
        "accessibility_level": 72.0,
        "competition_density": 65.0,
        "typical_cost_tier": "Budget",
        "typical_monthly_cost": 20000,
        "parking_support": "Moderate",
        "primary_customer_segments": ["Farmers", "Produce traders", "Retail grocers", "Wholesale buyers"],
        "business_affinities": {
            "Restaurant": 72, "Cafe": 60, "Grocery Store": 90, "Clothing Store": 50,
            "Pharmacy": 78, "Bakery": 68, "Gym": 30, "Electronics Store": 55,
            "Salon": 50, "Stationery Store": 65, "Farm Inputs / Tools": 98, "Other": 60
        }
    },
    {
        "id": "university_campuses",
        "name": "University Campuses & Student Residential Areas",
        "environment": "Education & Student",
        "description": "Campus precincts and student hostel neighborhoods with concentrated young adult demographics and tech-savvy preferences.",
        "footfall_level": 91.0,
        "accessibility_level": 82.0,
        "competition_density": 68.0,
        "typical_cost_tier": "Moderate",
        "typical_monthly_cost": 28000,
        "parking_support": "Moderate",
        "primary_customer_segments": ["University students", "Scholars", "Hostel residents", "Faculty"],
        "business_affinities": {
            "Restaurant": 88, "Cafe": 97, "Grocery Store": 80, "Clothing Store": 84,
            "Pharmacy": 82, "Bakery": 90, "Gym": 92, "Electronics Store": 86,
            "Salon": 85, "Stationery Store": 99, "Bookstore / Printing": 98, "Other": 75
        }
    },
    {
        "id": "entertainment_recreation_districts",
        "name": "Entertainment & Recreation Districts",
        "environment": "Leisure & Hospitality",
        "description": "Nightlife, gaming centers, cinemas, and entertainment venues attracting high discretionary recreational spend.",
        "footfall_level": 90.0,
        "accessibility_level": 85.0,
        "competition_density": 80.0,
        "typical_cost_tier": "Premium",
        "typical_monthly_cost": 60000,
        "parking_support": "High",
        "primary_customer_segments": ["Recreational spenders", "Youth", "Night owls", "Families on outing"],
        "business_affinities": {
            "Restaurant": 96, "Cafe": 94, "Grocery Store": 60, "Clothing Store": 82,
            "Pharmacy": 65, "Bakery": 88, "Gym": 82, "Electronics Store": 80,
            "Salon": 82, "Stationery Store": 55, "Arcade / VR / Games": 98, "Other": 70
        }
    },
    {
        "id": "sports_fitness_centres",
        "name": "Sports Complexes & Fitness Recreation Corridors",
        "environment": "Healthcare & Community",
        "description": "Surroundings of stadiums, sports academies, swimming centers, and community fitness grounds.",
        "footfall_level": 78.0,
        "accessibility_level": 84.0,
        "competition_density": 58.0,
        "typical_cost_tier": "Moderate",
        "typical_monthly_cost": 35000,
        "parking_support": "High",
        "primary_customer_segments": ["Athletes", "Fitness enthusiasts", "Sports fans", "Coaches & Youth"],
        "business_affinities": {
            "Restaurant": 78, "Cafe": 84, "Grocery Store": 72, "Clothing Store": 80,
            "Pharmacy": 84, "Bakery": 72, "Gym": 99, "Electronics Store": 70,
            "Salon": 72, "Stationery Store": 60, "Nutrition & Supplements": 98, "Other": 68
        }
    },
    {
        "id": "religious_pilgrimage_destinations",
        "name": "Religious Landmarks & Pilgrimage Destinations",
        "environment": "Leisure & Hospitality",
        "description": "Spiritual centers, temples, and shrines attracting large weekend and festival crowds seeking traditional goods and hospitality.",
        "footfall_level": 93.0,
        "accessibility_level": 78.0,
        "competition_density": 75.0,
        "typical_cost_tier": "Moderate",
        "typical_monthly_cost": 32000,
        "parking_support": "Moderate",
        "primary_customer_segments": ["Pilgrims", "Devotees", "Families", "Tourists"],
        "business_affinities": {
            "Restaurant": 86, "Cafe": 70, "Grocery Store": 75, "Clothing Store": 78,
            "Pharmacy": 85, "Bakery": 80, "Gym": 30, "Electronics Store": 55,
            "Salon": 52, "Stationery Store": 70, "Pooja Goods / Sweets": 99, "Other": 66
        }
    },
    {
        "id": "government_office_areas",
        "name": "Government Office Complexes & Secretariat Zones",
        "environment": "Civic & Mixed-Use",
        "description": "Administrative hubs with municipal buildings, courts, and collectorates generating routine civic foot traffic.",
        "footfall_level": 82.0,
        "accessibility_level": 88.0,
        "competition_density": 60.0,
        "typical_cost_tier": "Moderate",
        "typical_monthly_cost": 36000,
        "parking_support": "Moderate",
        "primary_customer_segments": ["Civic visitors", "Civil servants", "Legal professionals", "Contractors"],
        "business_affinities": {
            "Restaurant": 84, "Cafe": 86, "Grocery Store": 65, "Clothing Store": 60,
            "Pharmacy": 80, "Bakery": 80, "Gym": 65, "Electronics Store": 72,
            "Salon": 70, "Stationery Store": 96, "Printing / Legal Documentation": 99, "Other": 72
        }
    },
    {
        "id": "financial_banking_districts",
        "name": "Financial & Banking Districts",
        "environment": "Office & Corporate",
        "description": "High-capital banking avenues lined with major bank branches, brokerage houses, and wealth management centers.",
        "footfall_level": 80.0,
        "accessibility_level": 90.0,
        "competition_density": 70.0,
        "typical_cost_tier": "Premium",
        "typical_monthly_cost": 62000,
        "parking_support": "High",
        "primary_customer_segments": ["Investors", "High-net-worth clients", "Bankers", "Commercial clients"],
        "business_affinities": {
            "Restaurant": 88, "Cafe": 92, "Grocery Store": 62, "Clothing Store": 80,
            "Pharmacy": 76, "Bakery": 80, "Gym": 85, "Electronics Store": 80,
            "Salon": 84, "Stationery Store": 86, "Auditing & Wealth Management": 98, "Other": 76
        }
    },
    {
        "id": "convention_centres",
        "name": "Convention Centres & Exhibition Grounds",
        "environment": "Civic & Mixed-Use",
        "description": "Multi-acre event spaces hosting trade expos, industry summits, consumer fairs, and national conferences.",
        "footfall_level": 85.0,
        "accessibility_level": 90.0,
        "competition_density": 62.0,
        "typical_cost_tier": "Premium",
        "typical_monthly_cost": 55000,
        "parking_support": "High",
        "primary_customer_segments": ["Exhibitors", "Trade visitors", "Business delegates", "Event attendees"],
        "business_affinities": {
            "Restaurant": 90, "Cafe": 92, "Grocery Store": 55, "Clothing Store": 70,
            "Pharmacy": 74, "Bakery": 82, "Gym": 60, "Electronics Store": 75,
            "Salon": 75, "Stationery Store": 82, "Hospitality & Booth Services": 96, "Other": 72
        }
    },
    {
        "id": "airport_surroundings",
        "name": "Airport Surroundings & Aerocity Zones",
        "environment": "Transit & Transport",
        "description": "Aviation-adjacent developments featuring airport hotels, corporate headquarters, transit lounges, and high global connectivity.",
        "footfall_level": 84.0,
        "accessibility_level": 94.0,
        "competition_density": 66.0,
        "typical_cost_tier": "Premium",
        "typical_monthly_cost": 70000,
        "parking_support": "High",
        "primary_customer_segments": ["Airline crew", "Frequent flyers", "International travelers", "Corporate reps"],
        "business_affinities": {
            "Restaurant": 92, "Cafe": 95, "Grocery Store": 68, "Clothing Store": 84,
            "Pharmacy": 85, "Bakery": 85, "Gym": 86, "Electronics Store": 88,
            "Salon": 86, "Stationery Store": 70, "Car Rental / Executive Lounge": 98, "Other": 75
        }
    },
    {
        "id": "port_shipping_areas",
        "name": "Port & Shipping Maritime Areas",
        "environment": "Industrial & Logistics",
        "description": "Harbor and port-adjacent areas handling maritime cargo, customs brokering, and international freight container yards.",
        "footfall_level": 52.0,
        "accessibility_level": 86.0,
        "competition_density": 38.0,
        "typical_cost_tier": "Industrial",
        "typical_monthly_cost": 32000,
        "parking_support": "High",
        "primary_customer_segments": ["Customs brokers", "Ship chandlers", "Freight forwarders", "Port labor"],
        "business_affinities": {
            "Restaurant": 62, "Cafe": 52, "Grocery Store": 60, "Clothing Store": 30,
            "Pharmacy": 70, "Bakery": 55, "Gym": 40, "Electronics Store": 50,
            "Salon": 40, "Stationery Store": 60, "Marine Supplies / Shipping Agency": 99, "Other": 55
        }
    },
    {
        "id": "mixed_use_developments",
        "name": "Residential-Commercial Mixed-Use Townships",
        "environment": "Civic & Mixed-Use",
        "description": "Modern planned communities blending ground-floor retail, mid-tier offices, and residential towers in walkable zones.",
        "footfall_level": 82.0,
        "accessibility_level": 86.0,
        "competition_density": 65.0,
        "typical_cost_tier": "Moderate",
        "typical_monthly_cost": 40000,
        "parking_support": "High",
        "primary_customer_segments": ["Township residents", "Remote workers", "Families", "Commuters"],
        "business_affinities": {
            "Restaurant": 90, "Cafe": 92, "Grocery Store": 95, "Clothing Store": 85,
            "Pharmacy": 92, "Bakery": 92, "Gym": 90, "Electronics Store": 84,
            "Salon": 90, "Stationery Store": 86, "Community Services": 94, "Other": 80
        }
    },
    {
        "id": "emerging_commercial_developments",
        "name": "Emerging Commercial Growth Corridors",
        "environment": "Civic & Mixed-Use",
        "description": "Rapidly developing outer-ring bypass roads and planned smart city developments with rising property appreciation.",
        "footfall_level": 70.0,
        "accessibility_level": 84.0,
        "competition_density": 45.0,
        "typical_cost_tier": "Moderate",
        "typical_monthly_cost": 30000,
        "parking_support": "High",
        "primary_customer_segments": ["Early movers", "New homeowners", "Long-term investors", "Developers"],
        "business_affinities": {
            "Restaurant": 80, "Cafe": 82, "Grocery Store": 88, "Clothing Store": 75,
            "Pharmacy": 88, "Bakery": 84, "Gym": 85, "Electronics Store": 82,
            "Salon": 82, "Stationery Store": 80, "Home Improvement": 95, "Other": 78
        }
    }
]


def get_default_categories() -> List[Dict[str, Any]]:
    """Return the complete extensible catalogue of location categories."""
    return DEFAULT_LOCATION_CATEGORIES


def _infer_business_affinity(business_type: str, category_data: Dict[str, Any]) -> float:
    """Calculate affinity score between a business type and location category."""
    affinities = category_data.get("business_affinities", {})
    # Exact lookup
    if business_type in affinities:
        return float(affinities[business_type])
    
    # Case-insensitive lookup
    b_lower = business_type.strip().lower()
    for key, val in affinities.items():
        if key.lower() == b_lower:
            return float(val)

    # Keyword semantic match
    if any(k in b_lower for k in ["food", "dine", "eatery", "snack", "tiffin"]):
        return float(affinities.get("Restaurant", 85))
    if any(k in b_lower for k in ["coffee", "tea", "beverage", "lounge"]):
        return float(affinities.get("Cafe", 85))
    if any(k in b_lower for k in ["cloth", "fashion", "apparel", "wear", "garment"]):
        return float(affinities.get("Clothing Store", 80))
    if any(k in b_lower for k in ["med", "drug", "health", "pharma", "chem"]):
        return float(affinities.get("Pharmacy", 85))
    if any(k in b_lower for k in ["grocery", "supermarket", "provision", "kirana"]):
        return float(affinities.get("Grocery Store", 85))
    if any(k in b_lower for k in ["fit", "gym", "workout", "crossfit", "yoga"]):
        return float(affinities.get("Gym", 80))
    if any(k in b_lower for k in ["book", "station", "print", "xerox", "copy"]):
        return float(affinities.get("Stationery Store", 85))
    if any(k in b_lower for k in ["warehouse", "storage", "logistics", "courier"]):
        return float(affinities.get("Warehouse", 75 if category_data["environment"] == "Industrial & Logistics" else 35))

    return float(affinities.get("Other", 70.0))


def _calculate_customer_fit(target_customer: str, category_data: Dict[str, Any]) -> float:
    """Evaluate alignment between business target customer and category segments."""
    if not target_customer or target_customer.lower() in ("general public", "all", "general", ""):
        return 80.0
    
    target_tokens = set(target_customer.lower().replace(",", " ").split())
    segments = [s.lower() for s in category_data.get("primary_customer_segments", [])]
    
    match_count = 0
    for seg in segments:
        seg_tokens = set(seg.split())
        if target_tokens.intersection(seg_tokens):
            match_count += 1
            
    if match_count >= 2:
        return 95.0
    elif match_count == 1:
        return 88.0
    return 72.0


def _calculate_cost_viability(typical_cost: float, budget: Optional[float]) -> Tuple[float, Optional[str]]:
    """Evaluate affordability score based on profile budget."""
    if budget is None or budget <= 0:
        return 75.0, None
    
    ratio = typical_cost / budget
    if ratio <= 0.6:
        # Well within budget
        score = 95.0
        warning = None
    elif ratio <= 1.0:
        # Feasible within budget
        score = max(70.0, 95.0 - (ratio - 0.6) * 60.0)
        warning = None
    elif ratio <= 1.3:
        # Tight budget
        score = max(40.0, 70.0 - (ratio - 1.0) * 100.0)
        warning = f"Typical rent & operating cost (approx. ₹{typical_cost:,}/mo) stretches your stated monthly budget of ₹{budget:,}."
    else:
        # Budget deficit
        score = max(20.0, 40.0 - (ratio - 1.3) * 30.0)
        warning = f"Typical category costs (approx. ₹{typical_cost:,}/mo) exceed your stated budget of ₹{budget:,} by {((ratio-1)*100):.0f}%."
        
    return round(score, 1), warning


def recommend_default_locations(
    business_type: str,
    profile: Optional[BusinessProfile] = None,
    weights: Optional[Dict[str, float]] = None,
    environments: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Execute Default Recommendations methodology.
    
    Evaluates the 31+ location category archetypes against business type,
    profile constraints, and weights.
    """
    categories = DEFAULT_LOCATION_CATEGORIES
    if environments:
        env_set = set(environments)
        categories = [c for c in categories if c["environment"] in env_set]
        if not categories:
            categories = DEFAULT_LOCATION_CATEGORIES

    # Base factor weights
    w_affinity = (weights or {}).get("affinity", 0.30)
    w_footfall = (weights or {}).get("footfall", 0.20)
    w_accessibility = (weights or {}).get("accessibility", 0.15)
    w_customer = (weights or {}).get("customer_fit", 0.15)
    w_competition = (weights or {}).get("competition", 0.10)
    w_cost = (weights or {}).get("cost_viability", 0.10)

    total_w = w_affinity + w_footfall + w_accessibility + w_customer + w_competition + w_cost
    if total_w <= 0:
        total_w = 1.0
    w_affinity /= total_w
    w_footfall /= total_w
    w_accessibility /= total_w
    w_customer /= total_w
    w_competition /= total_w
    w_cost /= total_w

    target_cust = profile.target_customer if profile else ""
    budget = profile.budget if profile else None
    parking_req = profile.parking_required if profile else False
    req_space = profile.required_space_sqm if profile else None

    evaluated = []

    for cat in categories:
        affinity = _infer_business_affinity(business_type, cat)
        footfall = cat["footfall_level"]
        accessibility = cat["accessibility_level"]
        customer_fit = _calculate_customer_fit(target_cust, cat)
        
        # Agglomeration logic: Food, retail, cafes thrive in commercial density
        if business_type.lower() in ("restaurant", "cafe", "clothing store", "food street", "bakery"):
            competition_score = 50.0 + 0.5 * cat["competition_density"]
        else:
            competition_score = 100.0 - cat["competition_density"]

        cost_score, cost_warning = _calculate_cost_viability(cat["typical_monthly_cost"], budget)

        # Composite score
        score = (
            w_affinity * affinity +
            w_footfall * footfall +
            w_accessibility * accessibility +
            w_customer * customer_fit +
            w_competition * competition_score +
            w_cost * cost_score
        )

        strengths: List[str] = []
        weaknesses: List[str] = []
        warnings: List[str] = []

        if affinity >= 85:
            strengths.append(f"Strong category affinity: {cat['name']} has proven commercial traction for {business_type}.")
        if footfall >= 85:
            strengths.append(f"High visitor density: estimated footfall index is {footfall:.0f}/100.")
        if accessibility >= 85:
            strengths.append(f"Excellent arterial road and public transit connectivity ({accessibility:.0f}/100).")
        if customer_fit >= 88 and target_cust:
            strengths.append(f"Favorable customer segment alignment for '{target_cust}'.")
        if cost_score >= 85 and budget:
            strengths.append("Comfortably within your stated monthly budget.")

        if footfall < 60:
            weaknesses.append("Lower pedestrian traffic; rely more heavily on destination marketing and digital discovery.")
        if accessibility < 75:
            weaknesses.append("Transit access may require customer effort or personal vehicle transport.")
        if competition_score < 45:
            weaknesses.append("High competitive saturation; direct differentiation and distinct positioning needed.")
        if cost_score < 50:
            weaknesses.append("Higher real-estate occupancy overheads typical in this location archetype.")

        if cost_warning:
            warnings.append(cost_warning)
        if parking_req and cat.get("parking_support") == "Low":
            warnings.append("Stated parking requirement: this archetype often suffers from severe vehicle congestion and limited customer parking.")
        if req_space and req_space > 150 and cat.get("typical_cost_tier") == "Premium":
            warnings.append(f"Space requirement of {req_space} m² in a {cat['typical_cost_tier']} zone will command substantial upfront lease deposits.")

        if not strengths:
            strengths.append("Balanced baseline utility across commercial indicators.")
        if not weaknesses:
            weaknesses.append("No major structural weakness identified for this category archetype.")

        factors = [
            {"key": "affinity", "label": "Business Category Fit", "utility_score": round(affinity, 1), "weight": round(w_affinity, 3), "direction": "Higher is better"},
            {"key": "footfall", "label": "Customer Footfall Index", "utility_score": round(footfall, 1), "weight": round(w_footfall, 3), "direction": "Higher is better"},
            {"key": "accessibility", "label": "Transit & Road Accessibility", "utility_score": round(accessibility, 1), "weight": round(w_accessibility, 3), "direction": "Higher is better"},
            {"key": "customer_fit", "label": "Target Demographics Match", "utility_score": round(customer_fit, 1), "weight": round(w_customer, 3), "direction": "Higher is better"},
            {"key": "competition", "label": "Competitive Dynamic Score", "utility_score": round(competition_score, 1), "weight": round(w_competition, 3), "direction": "Domain-adjusted clustering/competition"},
            {"key": "cost_viability", "label": "Cost Affordability Index", "utility_score": round(cost_score, 1), "weight": round(w_cost, 3), "direction": "Lower cost vs budget is better"},
        ]

        next_steps = [
            f"Conduct peak-hour pedestrian and vehicle surveys in candidate {cat['name']} micro-markets.",
            f"Compare current commercial lease asks against benchmark ₹{cat['typical_monthly_cost']:,}/month.",
            "Verify municipal zoning permits, commercial signage rights, and utility capacities."
        ]

        classification = "High Suitability" if score >= 75 else "Moderate Suitability" if score >= 55 else "Low Suitability"

        evaluated.append({
            "id": cat["id"],
            "name": cat["name"],
            "category_name": cat["name"],
            "environment": cat["environment"],
            "score": round(score, 1),
            "classification": classification,
            "description": cat["description"],
            "factors": factors,
            "strengths": strengths[:3],
            "weaknesses": weaknesses[:3],
            "warnings": warnings,
            "next_steps": next_steps,
            "typical_cost_estimate": cat["typical_monthly_cost"],
            "customer_segments": cat["primary_customer_segments"],
            "methodology_note": "Rule-based category archetype MCDA scoring based on verified retail location principles."
        })

    # Sort deterministically
    evaluated.sort(key=lambda x: (-x["score"], x["name"].lower()))
    for rank, item in enumerate(evaluated, start=1):
        item["rank"] = rank

    return {
        "recommendations": evaluated,
        "total_categories_evaluated": len(evaluated),
        "business_type": business_type,
        "metadata": {
            "method": "Default Knowledge-Base Multi-Criteria Decision Analysis",
            "method_version": "2.0.0",
            "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
            "locations_evaluated": len(evaluated),
            "disclaimer": "Default recommendations provide general suitability guidance across established location archetypes. They reflect commercial principles rather than verified real-world property availability. Confirm local market conditions and lease terms on-ground."
        }
    }
