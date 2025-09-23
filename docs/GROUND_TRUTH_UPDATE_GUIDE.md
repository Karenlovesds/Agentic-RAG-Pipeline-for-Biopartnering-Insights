# Ground Truth Update Guide

This guide explains how to update your ground truth table and ensure the analysis dashboards continue to work correctly.

## Overview

Both the **Business Analysis** and **Market Analysis** dashboards are designed to be flexible and adaptable to changes in your ground truth data. They use a configuration system that makes them resilient to updates.

## Required Columns

The analysis dashboards expect the following columns in your ground truth Excel file:

### Core Columns (Required)
- `Generic name` - Generic drug name
- `Brand name` - Brand drug name  
- `FDA Approval` - FDA approval date
- `Drug Class` - Drug classification
- `Target` - Drug target
- `Mechanism` - Mechanism of action
- `Indication Approved` - Approved indications
- `Current Clinical Trials` - Current clinical trial information
- `Partner` - Company name
- `Tickets` - Number of analysis requests

### Column Mapping

The dashboards automatically map your Excel columns to internal names:

| Excel Column | Internal Name | Description |
|--------------|---------------|-------------|
| `Generic name` | `Generic Name` | Drug generic name |
| `Brand name` | `Brand Name` | Drug brand name |
| `FDA Approval` | `FDA Approval` | FDA approval date |
| `Drug Class` | `Drug Class` | Drug classification |
| `Target` | `Target` | Drug target |
| `Mechanism` | `Mechanism` | Mechanism of action |
| `Indication Approved` | `Indication Approved` | Approved indications |
| `Current Clinical Trials` | `Current Clinical Trials` | Clinical trial info |
| `Partner` | `Company` | Company name |
| `Tickets` | `Tickets` | Analysis request count |

## Updating Your Ground Truth Table

### 1. Add New Companies
Simply add new rows to your Excel file with all required columns filled out.

### 2. Add New Drugs
Add new rows for existing companies or new companies.

### 3. Update Existing Data
Modify any existing values - the dashboards will automatically reflect the changes.

### 4. Change Column Names
If you need to change column names, update the `COLUMN_MAPPING` in `config/analysis_config.py`:

```python
COLUMN_MAPPING = {
    'Your New Column Name': 'Internal Name',
    # ... other mappings
}
```

### 5. Add New Columns
If you add new columns that aren't used by the analysis, they will be ignored automatically.

## Configuration Customization

### Competition Thresholds
Adjust how targets are categorized by competition level:

```python
COMPETITION_THRESHOLDS = {
    'high_competition': 10,      # 10+ drugs = High Competition
    'medium_competition': 5,     # 5-9 drugs = Medium Competition  
    'low_competition': 2,        # 2-4 drugs = Low Competition
    'single_drug': 1             # 1 drug = Single Drug
}
```

### Priority Scoring Weights
Adjust how companies are prioritized:

```python
PRIORITY_WEIGHTS = {
    'ticket_volume': 0.4,        # 40% weight on ticket volume
    'drug_portfolio': 0.3,       # 30% weight on drug portfolio
    'fda_approvals': 0.2,        # 20% weight on FDA approvals
    'target_diversity': 0.1      # 10% weight on target diversity
}
```

### Time Allocation
Adjust resource allocation parameters:

```python
TIME_ALLOCATION = {
    'total_hours': 60,           # Total hours for allocation
    'base_hours_tickets': 40,    # Base hours based on ticket volume
    'adjustment_hours_priority': 20  # Adjustment hours based on priority
}
```

## File Location

The ground truth file should be located at:
```
data/Pipeline_Ground_Truth.xlsx
```

To change this location, update `GROUND_TRUTH_FILE` in `config/analysis_config.py`:

```python
GROUND_TRUTH_FILE = "path/to/your/file.xlsx"
```

## Data Validation

The dashboards automatically validate your data and will show error messages if:
- Required columns are missing
- The file cannot be found
- Data cannot be loaded

## Testing Your Updates

After updating your ground truth table:

1. **Check the dashboard**: Navigate to the Business Analysis or Market Analysis pages
2. **Look for error messages**: Any issues will be displayed at the top of the page
3. **Verify data**: Ensure all your new data appears correctly in the analysis

## Common Issues and Solutions

### Issue: "Missing required columns" error
**Solution**: Ensure all required columns are present in your Excel file with the correct names.

### Issue: "Ground Truth file not found" error
**Solution**: Check that the file is in the correct location (`data/Pipeline_Ground_Truth.xlsx`) or update the file path in the configuration.

### Issue: Data not appearing in analysis
**Solution**: Check that your data has the correct format (e.g., dates, numbers) and that required fields are not empty.

### Issue: Unexpected analysis results
**Solution**: Check your data for:
- Empty or missing values in key columns
- Incorrect data types (e.g., text in numeric fields)
- Special characters that might cause parsing issues

## Best Practices

1. **Keep a backup** of your original ground truth file
2. **Test changes** on a copy before updating the main file
3. **Validate data** before uploading to ensure all required fields are filled
4. **Use consistent formatting** for dates, numbers, and text fields
5. **Document changes** if you modify the column structure significantly

## Support

If you encounter issues updating your ground truth table:

1. Check the error messages in the dashboard
2. Verify your data format matches the requirements
3. Ensure all required columns are present
4. Check the configuration file for any custom settings

The analysis dashboards are designed to be robust and should handle most data updates automatically!
