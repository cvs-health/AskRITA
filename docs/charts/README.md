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
# Google Charts Implementation Guide

## Overview
Comprehensive documentation for implementing Google Charts with AskRITA's UniversalChartData model. Each chart type includes sample data structures, implementation code for vanilla JavaScript, React, and Angular frameworks.

## 📊 Available Chart Types

### Standard Charts

#### [Bar Chart (Horizontal)](./bar-chart.md)
**Perfect for:** Category comparison with long names
- Service area rankings
- Top performing stores
- Response volume by demographics
- **Use when:** Limited vertical space or long category names

#### [Column Chart (Vertical)](./column-chart.md)
**Perfect for:** Categorical data comparison over time
- Monthly survey responses
- Satisfaction by business unit
- Performance metrics comparison
- **Use when:** Standard comparison visualization needed

#### [Line Chart](./line-chart.md)
**Perfect for:** Trends over time and continuous data
- Satisfaction trends over time
- Response volume tracking
- Performance monitoring
- **Use when:** Time series analysis is primary focus

#### [Pie Chart & Donut Chart](./pie-chart.md)
**Perfect for:** Part-to-whole relationships
- NPS distribution (Promoters/Passives/Detractors)
- Response channel breakdown
- Satisfaction level distribution
- **Use when:** Showing proportions of a total (3-7 categories)

#### [Scatter Plot](./scatter-chart.md)
**Perfect for:** Correlation analysis between two variables
- Response time vs satisfaction
- Store size vs performance
- Demographics vs satisfaction
- **Use when:** Exploring relationships between numeric variables

### High-Impact Charts

#### [ComboChart (Bar-and-Line)](./combo-chart.md)
**Perfect for:** Volume + Quality metrics with dual Y-axes
- Response counts with NPS scores
- Customer volume with satisfaction metrics
- Campaign reach with engagement rates
- **Use when:** Different scales (10x+ difference) between metrics

#### [Gauge Charts](./gauge-chart.md)
**Perfect for:** Single KPI displays and dashboards
- Current NPS score with target zones
- Response rate percentages
- Performance indicators
- **Use when:** Real-time monitoring of single metrics

#### [GeoChart (Geographic Maps)](./geo-chart.md)
**Perfect for:** Regional analysis and location-based data
- Satisfaction scores by state/country
- Response distribution by geography
- Store performance by location
- **Use when:** Geographic patterns are important

### Advanced Visualizations

#### [Sankey Diagrams](./sankey-chart.md)
**Perfect for:** Flow analysis and customer journeys
- Survey completion funnels
- Customer journey mapping
- Process flow visualization
- **Use when:** Understanding paths and drop-offs

#### [TreeMap Charts](./treemap-chart.md)
**Perfect for:** Hierarchical data with quantities
- Response volume by service area and department
- Customer segments and sub-segments
- Market share analysis
- **Use when:** Part-to-whole relationships with hierarchy

#### [Timeline Charts](./timeline-chart.md)
**Perfect for:** Event sequences and project timelines
- Survey campaign schedules
- Customer journey events
- Project milestone tracking
- **Use when:** Showing duration and sequence of events

#### [Calendar Heatmap](./calendar-chart.md)
**Perfect for:** Daily patterns over extended periods
- Daily response volume patterns
- Satisfaction score trends by day
- Campaign activity calendar
- **Use when:** Identifying seasonal or daily patterns

#### [Histogram](./histogram-chart.md)
**Perfect for:** Data distribution analysis
- Response score distribution
- Response time analysis
- Customer demographics distribution
- **Use when:** Understanding data distribution and outliers

#### [Data Table with Sparklines](./table-chart.md)
**Perfect for:** Detailed data with embedded trends
- Store performance dashboards
- Customer segment analysis
- Campaign performance tracking
- **Use when:** Precise values needed alongside visual trends

## 🚀 Framework Integration

### [React Integration Guide](./react-integration.md)
Complete React implementation with:
- Custom hooks for chart management
- TypeScript support
- Component patterns
- Error boundaries
- Real-time updates
- Performance optimization

### [Angular Integration Guide](./angular-integration.md)
Complete Angular implementation with:
- Service-based architecture
- Dependency injection
- Component lifecycle management
- RxJS integration
- Testing strategies
- Dashboard patterns

## 🎯 Quick Start Examples

### Basic Implementation
```javascript
// Load Google Charts
google.charts.load('current', {'packages':['corechart', 'gauge', 'geochart']});
google.charts.setOnLoadCallback(drawChart);

function drawChart() {
    var data = google.visualization.arrayToDataTable([
        ['Category', 'Value'],
        ['Satisfied', 75],
        ['Neutral', 15],
        ['Dissatisfied', 10]
    ]);

    var options = {
        title: 'Customer Satisfaction Distribution'
    };

    var chart = new google.visualization.PieChart(document.getElementById('chart_div'));
    chart.draw(data, options);
}
```

### Ask RITA Integration
```python
# Using AskRITA's UniversalChartData
from askrita.sqlagent.formatters.DataFormatter import UniversalChartData, ChartDataset, DataPoint

chart_data = UniversalChartData(
    type="combo",
    title="Response Volume vs NPS Score",
    labels=["Commercial", "Medicare", "Medicaid"],
    datasets=[
        ChartDataset(
            label="Response Count",
            data=[
                DataPoint(y=15420, category="Commercial"),
                DataPoint(y=8932, category="Medicare"),
                DataPoint(y=5621, category="Medicaid")
            ],
            yAxisId="left-axis"
        ),
        ChartDataset(
            label="NPS Score",
            data=[
                DataPoint(y=72, category="Commercial"),
                DataPoint(y=68, category="Medicare"),
                DataPoint(y=45, category="Medicaid")
            ],
            yAxisId="right-axis"
        )
    ]
)
```

## 📋 Implementation Checklist

### For Each Chart Type
- [ ] **Data Structure** - Define UniversalChartData format
- [ ] **HTML Setup** - Create container element
- [ ] **Script Loading** - Load required Google Charts packages
- [ ] **Data Transformation** - Convert UniversalChartData to Google Charts format
- [ ] **Options Configuration** - Set up chart styling and behavior
- [ ] **Event Handling** - Add interactivity (optional)
- [ ] **Responsive Design** - Handle window resize events
- [ ] **Error Handling** - Graceful failure for missing data

### Framework-Specific
- [ ] **React**: Component lifecycle, hooks, TypeScript types — see [React Integration](react-integration.md)
- [ ] **Angular**: Services, dependency injection, observables — see [Angular Integration](angular-integration.md)

## 🎨 Design Guidelines

### Color Schemes
```javascript
// Brand Colors
const brandColors = {
    primary: '#1976D2',      // Blue
    secondary: '#FFFFFF',    // White
    accent: '#666666',       // Gray
    success: '#28a745',      // Green
    warning: '#ffc107',      // Yellow
    danger: '#dc3545'        // Red
};

// Satisfaction Score Colors
const satisfactionColors = {
    high: '#28a745',         // Green (80-100)
    medium: '#ffc107',       // Yellow (60-79)
    low: '#dc3545'          // Red (0-59)
};

// Multi-series Colors (accessible)
const seriesColors = [
    '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728',
    '#9467bd', '#8c564b', '#e377c2', '#7f7f7f'
];
```

### Typography
```javascript
const chartTypography = {
    title: {
        fontSize: 18,
        fontFamily: 'Arial, sans-serif',
        bold: true,
        color: '#333333'
    },
    axis: {
        fontSize: 12,
        fontFamily: 'Arial, sans-serif',
        color: '#666666'
    },
    legend: {
        fontSize: 11,
        fontFamily: 'Arial, sans-serif',
        color: '#333333'
    }
};
```

## 🔧 Common Patterns

### Data Loading Pattern
```javascript
async function loadChartData(endpoint) {
    try {
        const response = await fetch(endpoint);
        const universalData = await response.json();
        
        // Transform to Google Charts format
        const chartData = transformUniversalData(universalData);
        
        // Draw chart
        drawChart(chartData);
    } catch (error) {
        console.error('Failed to load chart data:', error);
        showErrorMessage('Unable to load chart data');
    }
}
```

### Responsive Chart Pattern
```javascript
function createResponsiveChart() {
    function drawChart() {
        const container = document.getElementById('chart_div');
        const width = container.offsetWidth;
        const height = Math.max(300, width * 0.6);
        
        const options = {
            ...baseOptions,
            width: width,
            height: height
        };
        
        chart.draw(data, options);
    }
    
    // Initial draw
    drawChart();
    
    // Redraw on resize
    window.addEventListener('resize', debounce(drawChart, 250));
}
```

### Error Handling Pattern
```javascript
function drawChartWithErrorHandling(data, options) {
    try {
        if (!data || data.length === 0) {
            showNoDataMessage();
            return;
        }
        
        const chart = new google.visualization.ComboChart(
            document.getElementById('chart_div')
        );
        
        google.visualization.events.addListener(chart, 'error', function(error) {
            console.error('Chart error:', error);
            showErrorMessage('Chart rendering failed');
        });
        
        chart.draw(data, options);
    } catch (error) {
        console.error('Chart initialization error:', error);
        showErrorMessage('Chart initialization failed');
    }
}
```

## 📚 Additional Resources

### Google Charts Documentation
- [Google Charts Gallery](https://developers.google.com/chart/interactive/docs/gallery)
- [Configuration Options](https://developers.google.com/chart/interactive/docs/customizing_charts)
- [Event Handling](https://developers.google.com/chart/interactive/docs/events)

### Ask RITA Integration
- [Configuration Options](../configuration/workflow.md#combined-visualization-step-new-in-v062)

### Best Practices
- [Accessibility Guidelines](https://developers.google.com/chart/interactive/docs/accessibility)
- [Performance Optimization](https://developers.google.com/chart/interactive/docs/performance)
- [Mobile Responsiveness](https://developers.google.com/chart/interactive/docs/basic_customizing#responsive-charts)

## 🎯 Chart Selection Guide

### By Data Type
- **Categorical Data**: Bar, Column, Pie charts
- **Time Series**: Line, Area, Calendar charts
- **Geographic**: GeoChart
- **Hierarchical**: TreeMap
- **Flow/Process**: Sankey
- **Distribution**: Histogram
- **Single Metrics**: Gauge
- **Multi-dimensional**: ComboChart, Scatter
- **Detailed Data**: Table with Sparklines

### By Use Case
- **Executive Dashboard**: Gauge, ComboChart, Table with Sparklines
- **Regional Analysis**: GeoChart, TreeMap
- **Customer Journey**: Sankey, Timeline
- **Performance Tracking**: Line, ComboChart, Calendar
- **Market Analysis**: TreeMap, GeoChart, Scatter
- **Satisfaction Surveys**: Gauge, Bar, ComboChart, Histogram
- **Campaign Management**: Timeline, Calendar, Table
- **Data Distribution**: Histogram, Scatter

### By Audience
- **Executives**: Simple, high-level (Gauge, ComboChart, Pie)
- **Analysts**: Detailed, interactive (Sankey, TreeMap, Scatter, Histogram)
- **Operations**: Real-time, actionable (Gauge, Line, Calendar)
- **Marketing**: Engaging, visual (GeoChart, TreeMap, Timeline)
- **Data Scientists**: Statistical, exploratory (Histogram, Scatter, Table)

### By Data Size
- **Small Datasets** (<50 points): Pie, Bar, Column
- **Medium Datasets** (50-500 points): Line, Scatter, TreeMap
- **Large Datasets** (500+ points): Histogram, Calendar, aggregated charts
- **Time Series**: Line, Calendar (any size with aggregation)
- **Geographic**: GeoChart (scales well with proper aggregation)

## 📊 Google Charts Quick Reference

| # | Chart Type | Link |
|---|-----------|------|
| 1 | Bar-and-Line Chart | https://developers.google.com/chart/interactive/docs/gallery/combochart |
| 2 | Multi-Series Line Chart | https://developers.google.com/chart/interactive/docs/gallery/linechart |
| 3 | Grouped Column Chart | https://developers.google.com/chart/interactive/docs/gallery/columnchart |
| 4 | Horizontal Bar Chart | https://developers.google.com/chart/interactive/docs/gallery/barchart |
| 5 | Data Table with Sparklines | https://developers.google.com/chart/interactive/docs/gallery/table |
| 6 | Donut Chart | https://developers.google.com/chart/interactive/docs/gallery/piechart |
| 7 | Scatter Plot | https://developers.google.com/chart/interactive/docs/gallery/scatterchart |
| 8 | Stacked Area Chart | https://developers.google.com/chart/interactive/docs/gallery/areachart |
| 9 | Geographic Map | https://developers.google.com/chart/interactive/docs/gallery/geochart |
| 10 | Gauge Meter | https://developers.google.com/chart/interactive/docs/gallery/gauge |
| 11 | Flow Diagram | https://developers.google.com/chart/interactive/docs/gallery/sankey |
| 12 | Hierarchical Rectangles | https://developers.google.com/chart/interactive/docs/gallery/treemap |
| 13 | Event Timeline | https://developers.google.com/chart/interactive/docs/gallery/timeline |
| 14 | Calendar Heatmap | https://developers.google.com/chart/interactive/docs/gallery/calendar |
| 15 | Distribution Histogram | https://developers.google.com/chart/interactive/docs/gallery/histogram |
| 16 | Multi-Chart Dashboard | https://developers.google.com/chart/interactive/docs/gallery/controls |
| 17 | Interactive Controls | https://developers.google.com/chart/interactive/docs/gallery/controls |
| 18 | Linked Chart Views | https://developers.google.com/chart/interactive/docs/gallery/controls |

**Additional Resources:**
- [All Chart Types Gallery](https://developers.google.com/chart/interactive/docs/gallery)
- [Dashboard Tutorial](https://developers.google.com/chart/interactive/docs/gallery/controls)
- [Dual Y-Axis Examples](https://developers.google.com/chart/interactive/docs/gallery/combochart#dual-y-charts)

---

This comprehensive guide provides everything needed to implement professional-grade chart visualizations using Google Charts with Ask RITA's data structures!
