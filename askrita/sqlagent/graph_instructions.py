# Copyright 2026 CVS Health and/or one of its affiliates
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Chart-type-specific formatting instructions for LLM-driven visualization."""

barGraphIntstruction = """

  Where data is: {
    labels: string[]
    values: { data: number[], label: string }[]
  }

// Examples of usage:
Each label represents a column on the x axis.
Each array in values represents a different entity.

Here we are looking at average income for each month.
1. data = {
  labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
  values: [{data:[21.5, 25.0, 47.5, 64.8, 105.5, 133.2], label: 'Income'}],
}

Here we are looking at the performance of american and european players for each series. Since there are two entities, we have two arrays in values.
2. data = {
  labels: ['series A', 'series B', 'series C'],
  values: [{data:[10, 15, 20], label: 'American'}, {data:[20, 25, 30], label: 'European'}],
}
"""

horizontalBarGraphIntstruction = """

  Where data is: {
    labels: string[]
    values: { data: number[], label: string }[]
  }

// Examples of usage:
Each label represents a column on the x axis.
Each array in values represents a different entity.

Here we are looking at average income for each month.
1. data = {
  labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
  values: [{data:[21.5, 25.0, 47.5, 64.8, 105.5, 133.2], label: 'Income'}],
}

Here we are looking at the performance of american and european players for each series. Since there are two entities, we have two arrays in values.
2. data = {
  labels: ['series A', 'series B', 'series C'],
  values: [{data:[10, 15, 20], label: 'American'}, {data:[20, 25, 30], label: 'European'}],
}

"""


lineGraphIntstruction = """

  Where data is: {
  xValues: number[] | string[]
  yValues: { data: number[]; label: string }[]
}

// Examples of usage:

Here we are looking at the momentum of a body as a function of mass.
1. data = {
  xValues: ['2020', '2021', '2022', '2023', '2024'],
  yValues: [
    { data: [2, 5.5, 2, 8.5, 1.5]},
  ],
}

Here we are looking at the performance of american and european players for each year. Since there are two entities, we have two arrays in yValues.
2. data = {
  xValues: ['2020', '2021', '2022', '2023', '2024'],
  yValues: [
    { data: [2, 5.5, 2, 8.5, 1.5], label: 'American' },
    { data: [2, 5.5, 2, 8.5, 1.5], label: 'European' },
  ],
}
"""

pieChartIntstruction = """

  Where data is: {
    labels: string
    values: number
  }[]

// Example usage:
 data = [
        { id: 0, value: 10, label: 'series A' },
        { id: 1, value: 15, label: 'series B' },
        { id: 2, value: 20, label: 'series C' },
      ],
"""

scatterPlotIntstruction = """
Where data is: {
  series: {
    data: { x: number; y: number; id: number }[]
    label: string
  }[]
}

// Examples of usage:
1. Here each data array represents the points for a different entity.
We are looking for correlation between amount spent and quantity bought for men and women.
data = {
  series: [
    {
      data: [
        { x: 100, y: 200, id: 1 },
        { x: 120, y: 100, id: 2 },
        { x: 170, y: 300, id: 3 },
      ],
      label: 'Men',
    },
    {
      data: [
        { x: 300, y: 300, id: 1 },
        { x: 400, y: 500, id: 2 },
        { x: 200, y: 700, id: 3 },
      ],
      label: 'Women',
    }
  ],
}

2. Here we are looking for correlation between the height and weight of players.
data = {
  series: [
    {
      data: [
        { x: 180, y: 80, id: 1 },
        { x: 170, y: 70, id: 2 },
        { x: 160, y: 60, id: 3 },
      ],
      label: 'Players',
    },
  ],
}

// Note: Each object in the 'data' array represents a point on the scatter plot.
// The 'x' and 'y' values determine the position of the point, and 'id' is a unique identifier.
// Multiple series can be represented, each as an object in the outer array.
"""

areaGraphInstruction = """

  Where data is: {
  xValues: number[] | string[]
  yValues: { data: number[]; label: string; fill?: boolean }[]
}

// Examples of usage:
// Area charts are filled line charts that show trends over time with emphasis on cumulative values

1. data = {
  xValues: ['Jan', 'Feb', 'Mar', 'Apr', 'May'],
  yValues: [
    { data: [20, 30, 25, 40, 35], label: 'Revenue', fill: true },
  ],
}

2. data = {
  xValues: ['Q1', 'Q2', 'Q3', 'Q4'],
  yValues: [
    { data: [100, 120, 90, 150], label: 'Product A', fill: true },
    { data: [80, 90, 110, 120], label: 'Product B', fill: true },
  ],
}
"""

donutChartInstruction = """

  Where data is: {
    id: number
    value: number
    label: string
    innerRadius?: number
    outerRadius?: number
  }[]

// Example usage:
// Donut charts are pie charts with a hollow center, ideal for showing proportions with central metric

data = [
  { id: 0, value: 35, label: 'Desktop', innerRadius: 40, outerRadius: 80 },
  { id: 1, value: 45, label: 'Mobile', innerRadius: 40, outerRadius: 80 },
  { id: 2, value: 20, label: 'Tablet', innerRadius: 40, outerRadius: 80 },
]
"""

radarChartInstruction = """

  Where data is: {
  labels: string[]
  datasets: {
    label: string
    data: number[]
    backgroundColor?: string
    borderColor?: string
  }[]
}

// Example usage:
// Radar charts show multi-dimensional data on a circular grid

data = {
  labels: ['Speed', 'Reliability', 'Comfort', 'Safety', 'Efficiency'],
  datasets: [
    {
      label: 'Car A',
      data: [4, 3, 4, 2, 3],
      backgroundColor: 'rgba(255, 99, 132, 0.2)',
      borderColor: 'rgba(255, 99, 132, 1)',
    },
    {
      label: 'Car B',
      data: [3, 4, 3, 4, 4],
      backgroundColor: 'rgba(54, 162, 235, 0.2)',
      borderColor: 'rgba(54, 162, 235, 1)',
    }
  ]
}
"""

heatmapInstruction = """

  Where data is: {
  xLabels: string[]
  yLabels: string[]
  data: { x: number; y: number; value: number }[]
}

// Example usage:
// Heatmaps show intensity of data through colors in a matrix format

data = {
  xLabels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'],
  yLabels: ['9AM', '12PM', '3PM', '6PM'],
  data: [
    { x: 0, y: 0, value: 12 },
    { x: 1, y: 0, value: 15 },
    { x: 2, y: 0, value: 8 },
    // ... more data points
  ]
}
"""

bubbleChartInstruction = """

  Where data is: {
  series: {
    data: { x: number; y: number; size: number; id: number }[]
    label: string
  }[]
}

// Example usage:
// Bubble charts are scatter plots with a third dimension (size)

data = {
  series: [
    {
      data: [
        { x: 100, y: 200, size: 30, id: 1 },
        { x: 120, y: 100, size: 20, id: 2 },
        { x: 170, y: 300, size: 40, id: 3 },
      ],
      label: 'Dataset 1',
    }
  ],
}
"""

gaugeChartInstruction = """

  Where data is: {
  value: number
  min: number
  max: number
  label: string
  thresholds?: { value: number; color: string }[]
}

// Example usage:
// Gauge charts show a single value within a range

data = {
  value: 75,
  min: 0,
  max: 100,
  label: 'Performance Score',
  thresholds: [
    { value: 30, color: 'red' },
    { value: 70, color: 'yellow' },
    { value: 90, color: 'green' }
  ]
}
"""

funnelChartInstruction = """

  Where data is: {
  label: string
  value: number
  percentage?: number
}[]

// Example usage:
// Funnel charts show progressive reduction of data (conversion flows)

data = [
  { label: 'Awareness', value: 10000, percentage: 100 },
  { label: 'Interest', value: 7500, percentage: 75 },
  { label: 'Consideration', value: 5000, percentage: 50 },
  { label: 'Purchase', value: 2500, percentage: 25 },
]
"""

treemapInstruction = """

  Where data is: {
  name: string
  value: number
  children?: TreemapData[]
}[]

// Example usage:
// Treemaps show hierarchical data using nested rectangles

data = [
  {
    name: 'Technology',
    value: 150,
    children: [
      { name: 'Software', value: 80 },
      { name: 'Hardware', value: 70 }
    ]
  },
  {
    name: 'Healthcare',
    value: 120,
    children: [
      { name: 'Pharmaceuticals', value: 60 },
      { name: 'Medical Devices', value: 60 }
    ]
  }
]
"""

waterfallInstruction = """

  Where data is: {
  label: string
  value: number
  type: 'positive' | 'negative' | 'total'
}[]

// Example usage:
// Waterfall charts show cumulative effect of sequential positive or negative values

data = [
  { label: 'Starting Revenue', value: 100, type: 'total' },
  { label: 'Q1 Growth', value: 20, type: 'positive' },
  { label: 'Q2 Decline', value: -10, type: 'negative' },
  { label: 'Q3 Growth', value: 15, type: 'positive' },
  { label: 'Final Revenue', value: 125, type: 'total' },
]
"""

histogramInstruction = """

  Where data is: {
  bins: { start: number; end: number; count: number }[]
  binWidth: number
}

// Example usage:
// Histograms show frequency distribution of continuous data

data = {
  bins: [
    { start: 0, end: 10, count: 5 },
    { start: 10, end: 20, count: 12 },
    { start: 20, end: 30, count: 18 },
    { start: 30, end: 40, count: 8 },
  ],
  binWidth: 10
}
"""

boxPlotInstruction = """

  Where data is: {
  label: string
  min: number
  q1: number
  median: number
  q3: number
  max: number
  outliers?: number[]
}[]

// Example usage:
// Box plots show statistical distribution with quartiles

data = [
  {
    label: 'Dataset A',
    min: 10, q1: 25, median: 35, q3: 45, max: 60,
    outliers: [5, 65]
  },
  {
    label: 'Dataset B',
    min: 15, q1: 30, median: 40, q3: 50, max: 65,
    outliers: [10]
  }
]
"""

candlestickInstruction = """

  Where data is: {
  date: string
  open: number
  high: number
  low: number
  close: number
}[]

// Example usage:
// Candlestick charts show financial data (OHLC)

data = [
  { date: '2023-01-01', open: 100, high: 110, low: 95, close: 105 },
  { date: '2023-01-02', open: 105, high: 115, low: 102, close: 112 },
  { date: '2023-01-03', open: 112, high: 118, low: 108, close: 115 },
]
"""

polarAreaInstruction = """

  Where data is: {
  labels: string[]
  values: number[]
  backgroundColor?: string[]
}

// Example usage:
// Polar area charts are like pie charts but with varying radii

data = {
  labels: ['Red', 'Green', 'Yellow', 'Grey', 'Blue'],
  values: [11, 16, 7, 3, 14],
  backgroundColor: [
    'rgba(255, 99, 132, 0.5)',
    'rgba(75, 192, 192, 0.5)',
    'rgba(255, 205, 86, 0.5)',
    'rgba(201, 203, 207, 0.5)',
    'rgba(54, 162, 235, 0.5)'
  ]
}
"""

sankeyInstruction = """

  Where data is: {
  nodes: { id: string; label: string }[]
  links: { source: string; target: string; value: number }[]
}

// Example usage:
// Sankey diagrams show flow between nodes

data = {
  nodes: [
    { id: 'a', label: 'Source A' },
    { id: 'b', label: 'Source B' },
    { id: 'x', label: 'Target X' },
    { id: 'y', label: 'Target Y' }
  ],
  links: [
    { source: 'a', target: 'x', value: 10 },
    { source: 'a', target: 'y', value: 20 },
    { source: 'b', target: 'x', value: 15 },
    { source: 'b', target: 'y', value: 25 }
  ]
}
"""

sunburstInstruction = """

  Where data is: {
  name: string
  value?: number
  children?: SunburstData[]
}[]

// Example usage:
// Sunburst charts show hierarchical data in concentric circles

data = [
  {
    name: 'Level 1',
    children: [
      {
        name: 'Level 2A',
        value: 30,
        children: [
          { name: 'Level 3A', value: 15 },
          { name: 'Level 3B', value: 15 }
        ]
      },
      { name: 'Level 2B', value: 20 }
    ]
  }
]
"""

graph_instructions = {
    "bar": barGraphIntstruction,
    "horizontal_bar": horizontalBarGraphIntstruction,
    "line": lineGraphIntstruction,
    "pie": pieChartIntstruction,
    "scatter": scatterPlotIntstruction,
    "area": areaGraphInstruction,
    "donut": donutChartInstruction,
    "radar": radarChartInstruction,
    "heatmap": heatmapInstruction,
    "bubble": bubbleChartInstruction,
    "gauge": gaugeChartInstruction,
    "funnel": funnelChartInstruction,
    "treemap": treemapInstruction,
    "waterfall": waterfallInstruction,
    "histogram": histogramInstruction,
    "box": boxPlotInstruction,
    "candlestick": candlestickInstruction,
    "polar": polarAreaInstruction,
    "sankey": sankeyInstruction,
    "sunburst": sunburstInstruction,
}
