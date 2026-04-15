<!--
  © 2026 CVS Health and/or one of its affiliates. All rights reserved.

  Licensed under the Apache License, Version 2.0 (the "License");
  you may not use this file except in compliance with the License.
  You may obtain a copy of the License at

      http://www.apache.org/licenses/LICENSE-2.0

  Unless required by applicable law or agreed to in writing, software
  distributed under the License is distributed on an "AS IS" BASIS,
  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
  See the License for the specific language governing permissions and
  limitations under the License.
-->
# Schema Descriptions Configuration

The hybrid schema descriptions system combines automatic metadata extraction with manual enhancements to improve SQL generation quality.

The hybrid schema descriptions system combines automatic metadata extraction with manual enhancements to dramatically improve SQL generation quality. This feature is currently available for BigQuery and will be extended to other databases in future releases.

## Key Benefits

- **🚀 Better SQL Generation**: Rich schema context leads to more accurate and efficient queries
- **⚡ Automatic Extraction**: Leverages existing database metadata and comments
- **🎯 Manual Control**: Override or supplement automatic descriptions where needed
- **📚 Business Glossary**: Define domain-specific terms for AI understanding
- **🔄 Hybrid Approach**: Best of both automated and manual approaches

## Configuration Structure

```yaml
database:
  schema_descriptions:
    # High-level context about your data domain
    project_context: "Enterprise e-commerce data warehouse for analytics and reporting"
    
    # Automatic extraction from database metadata
    automatic_extraction:
      enabled: true                         # Enable automatic extraction
      fallback_to_column_name: true        # Generate descriptions from column names
      include_data_types: true             # Include data types in descriptions
      extract_comments: true               # Use existing database comments
    
    # Manual column descriptions (enhance automatic ones)
    columns:
      customer_id:
        description: "Unique customer identifier linking all customer data"
        mode: "supplement"                  # How to combine with automatic descriptions
        business_context: "Primary key used across all customer analytics and segmentation"
      
      order_total:
        description: "Complete order value including all taxes, fees, and discounts"
        mode: "override"                    # Replace automatic description entirely
        business_context: "Critical revenue metric for financial reporting and analysis"
    
    # Manual table descriptions
    tables:
      customers:
        description: "Master customer database with complete profile information"
        business_purpose: "Customer relationship management and marketing personalization"
      
      orders:
        description: "Complete transaction history for all customer purchases"
        business_purpose: "Revenue analysis, customer behavior tracking, and business intelligence"
    
    # Business glossary for domain-specific terms
    business_terms:
      churn: "Customer who hasn't made a purchase in the last 90 days"
      ltv: "Customer Lifetime Value - predicted total revenue from customer relationship"
      conversion_rate: "Percentage of website visitors who complete a purchase"
      cohort: "Group of customers acquired during the same time period"
```

## Description Modes

The `mode` parameter controls how manual descriptions are combined with automatic ones:

| Mode | Behavior | Use Case |
|------|----------|----------|
| **`supplement`** | Combines automatic + manual descriptions | Enhance existing metadata with business context |
| **`override`** | Replaces automatic description entirely | Completely replace inadequate automatic descriptions |
| **`fallback`** | Uses manual only if no automatic description exists | Provide backup descriptions for undocumented columns |
| **`auto_only`** | Ignores manual description, uses only automatic | Trust database metadata completely |

## Example Use Cases

**E-commerce Analytics:**
```yaml
schema_descriptions:
  project_context: "E-commerce platform analytics for customer behavior and sales optimization"
  columns:
    customer_segment:
      description: "Customer classification based on purchase behavior and value"
      mode: "supplement"
      business_context: "Drives personalized marketing campaigns and pricing strategies"
  business_terms:
    abandoned_cart: "Shopping cart with items but no completed purchase within 24 hours"
    cross_sell: "Additional products recommended based on current purchase"
```

**Financial Services:**
```yaml
schema_descriptions:
  project_context: "Financial services data warehouse for risk analysis and compliance"
  columns:
    risk_score:
      description: "Calculated risk assessment score for credit decisions"
      mode: "override"
      business_context: "Primary metric for loan approval workflows and regulatory reporting"
  business_terms:
    aml: "Anti-Money Laundering compliance monitoring and reporting"
    kyc: "Know Your Customer verification and documentation process"
```

**Healthcare Analytics:**
```yaml
schema_descriptions:
  project_context: "Healthcare analytics for patient outcomes and operational efficiency"
  columns:
    patient_id:
      description: "De-identified patient identifier for HIPAA compliance"
      mode: "supplement"
      business_context: "Links patient data while maintaining privacy requirements"
  business_terms:
    readmission: "Patient return within 30 days of discharge"
    los: "Length of Stay - total days patient remained in facility"
```

## Best Practices

**1. Start with Automatic Extraction**
```yaml
# Enable automatic extraction first
automatic_extraction:
  enabled: true
  fallback_to_column_name: true
  include_data_types: true
  extract_comments: true
```

**2. Add Strategic Manual Enhancements**
```yaml
# Focus on key business metrics and unclear columns
columns:
  # Critical business metrics
  revenue:
    mode: "supplement"
    business_context: "Primary KPI for executive reporting"
  
  # Technical columns needing clarification
  status_cd:
    description: "Order processing status code"
    mode: "override"
    business_context: "Critical for order fulfillment workflow"
```

**3. Build a Comprehensive Business Glossary**
```yaml
business_terms:
  # Domain-specific calculations
  cac: "Customer Acquisition Cost - total marketing spend per new customer"
  mrr: "Monthly Recurring Revenue from subscription customers"
  
  # Process definitions
  fulfillment: "Complete order processing from payment to delivery"
  returns: "Product returns within 30-day return window"
```

**4. Provide Domain Context**
```yaml
project_context: |
  Enterprise data warehouse supporting:
  - Customer analytics and segmentation
  - Sales performance and forecasting  
  - Marketing campaign optimization
  - Financial reporting and compliance
```

