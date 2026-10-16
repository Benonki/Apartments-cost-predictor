# Apartments cost predictor App

A Python-based application for analyzing and predicting apartment prices in Poland and Melbourne, helping users explore price trends, compare locations, and understand the factors affecting real estate prices.

## 📈 Datasets

### 1. Apartment Prices in Poland

**Dataset**: `Apartment Prices in Poland`

**Author**: Krzysztof Jamroz

**Source**: Kaggle

**License**: Apache License 2.0

**License details**: https://www.apache.org/licenses/LICENSE-2.0

### 2. Melbourne Housing Snapshot

**Dataset**: `Melbourne Housing Snapshot`

**Author**: DanB (Dan Becker); based on the original Melbourne housing dataset by Tony Pino

**Source**: Kaggle

**License**: Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)

**License details**: https://creativecommons.org/licenses/by-nc-sa/4.0/

**Description**: A snapshot of Melbourne real estate sales data, including property prices, suburbs, property types, rooms, sale dates, and other property characteristics.

**Usage note**: Attribution is required; use is restricted to non-commercial purposes, and distributed adaptations must follow the ShareAlike terms of the license.

## ⚙️ Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/Benonki/Apartments-cost-predictor.git
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
   - If you update the project, refresh `requirements.txt`:
     ```bash
     pip freeze > requirements.txt
      ```

## 🚀 Running the App

1. Run `csv_to_db.py` script:
   ```bash
   python csv_to_db.py
   ```
2. Start the desktop app:
   ```bash
   python main.py
   ```
   
