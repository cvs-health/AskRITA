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
# Google Charts with React Framework

## Overview
Complete guide for integrating Google Charts with React applications, including TypeScript support, component patterns, and best practices for survey data visualization.

## Installation & Setup

### Install Dependencies
```bash
# Core React dependencies
npm install react react-dom

# TypeScript support (optional but recommended)
npm install -D @types/react @types/react-dom @types/google.visualization

# Alternative: Use react-google-charts wrapper
npm install react-google-charts
```

### Load Google Charts Library
```tsx
// Method 1: Load in index.html
// Add to public/index.html
<script type="text/javascript" src="https://www.gstatic.com/charts/loader.js"></script>

// Method 2: Dynamic loading in React
import { useEffect } from 'react';

const loadGoogleCharts = (): Promise<void> => {
  return new Promise((resolve) => {
    if (window.google && window.google.charts) {
      resolve();
      return;
    }

    const script = document.createElement('script');
    script.src = 'https://www.gstatic.com/charts/loader.js';
    script.onload = () => {
      window.google.charts.load('current', {
        packages: ['corechart', 'gauge', 'geochart', 'sankey', 'treemap', 'timeline', 'calendar', 'table']
      });
      window.google.charts.setOnLoadCallback(() => resolve());
    };
    document.head.appendChild(script);
  });
};
```

## Base Chart Component

### Generic Chart Hook
```tsx
// hooks/useGoogleChart.ts
import { useEffect, useRef, useState } from 'react';

interface UseGoogleChartProps {
  chartType: string;
  data: any[][];
  options: any;
  packages?: string[];
}

export const useGoogleChart = ({
  chartType,
  data,
  options,
  packages = ['corechart']
}: UseGoogleChartProps) => {
  const chartRef = useRef<HTMLDivElement>(null);
  const [isLoaded, setIsLoaded] = useState(false);

  useEffect(() => {
    const loadChart = async () => {
      if (!window.google) {
        await loadGoogleCharts();
      }

      if (!window.google.charts) {
        window.google.charts.load('current', { packages });
        await new Promise(resolve => {
          window.google.charts.setOnLoadCallback(resolve);
        });
      }

      setIsLoaded(true);
    };

    loadChart();
  }, [packages]);

  useEffect(() => {
    if (!isLoaded || !chartRef.current) return;

    const chartData = google.visualization.arrayToDataTable(data);
    const chart = new google.visualization[chartType](chartRef.current);
    chart.draw(chartData, options);
  }, [isLoaded, chartType, data, options]);

  return chartRef;
};
```

## Chart Components

### ComboChart Component
```tsx
// components/ComboChart.tsx
import React from 'react';
import { useGoogleChart } from '../hooks/useGoogleChart';

interface ComboChartData {
  category: string;
  volume: number;
  score: number;
}

interface ComboChartProps {
  data: ComboChartData[];
  title?: string;
  width?: number;
  height?: number;
  volumeLabel?: string;
  scoreLabel?: string;
}

export const ComboChart: React.FC<ComboChartProps> = ({
  data,
  title = "Volume vs Score Analysis",
  width = 900,
  height = 500,
  volumeLabel = "Volume",
  scoreLabel = "Score"
}) => {
  const chartData = [
    ['Category', volumeLabel, scoreLabel],
    ...data.map(item => [item.category, item.volume, item.score])
  ];

  const options = {
    title,
    width,
    height,
    vAxes: {
      0: {
        title: volumeLabel,
        textStyle: { color: '#1f77b4' },
        titleTextStyle: { color: '#1f77b4' },
        format: '#,###'
      },
      1: {
        title: scoreLabel,
        textStyle: { color: '#ff7f0e' },
        titleTextStyle: { color: '#ff7f0e' },
        minValue: 0,
        maxValue: 100
      }
    },
    series: {
      0: { type: 'columns', targetAxisIndex: 0, color: '#1f77b4' },
      1: { type: 'line', targetAxisIndex: 1, color: '#ff7f0e', lineWidth: 3 }
    },
    legend: { position: 'top', alignment: 'center' },
    chartArea: { left: 80, top: 80, width: '75%', height: '70%' }
  };

  const chartRef = useGoogleChart({
    chartType: 'ComboChart',
    data: chartData,
    options
  });

  return <div ref={chartRef} className="combo-chart" />;
};

// Usage Example
const App = () => {
  const surveyData = [
    { category: "Commercial", volume: 15420, score: 72 },
    { category: "Medicare", volume: 8932, score: 68 },
    { category: "Medicaid", volume: 5621, score: 45 },
    { category: "Individual", volume: 2103, score: 38 }
  ];

  return (
    <div>
      <h1>Survey Analysis Dashboard</h1>
      <ComboChart 
        data={surveyData}
        title="Response Volume vs NPS Score by Segment"
        volumeLabel="Response Count"
        scoreLabel="NPS Score"
      />
    </div>
  );
};
```

### Gauge Component
```tsx
// components/GaugeChart.tsx
import React from 'react';
import { useGoogleChart } from '../hooks/useGoogleChart';

interface GaugeChartProps {
  value: number;
  label: string;
  min?: number;
  max?: number;
  redZone?: [number, number];
  yellowZone?: [number, number];
  greenZone?: [number, number];
  width?: number;
  height?: number;
}

export const GaugeChart: React.FC<GaugeChartProps> = ({
  value,
  label,
  min = 0,
  max = 100,
  redZone = [0, 30],
  yellowZone = [30, 70],
  greenZone = [70, 100],
  width = 400,
  height = 300
}) => {
  const chartData = [
    ['Label', 'Value'],
    [label, value]
  ];

  const options = {
    title: `Current ${label}`,
    width,
    height,
    redFrom: redZone[0],
    redTo: redZone[1],
    yellowFrom: yellowZone[0],
    yellowTo: yellowZone[1],
    greenFrom: greenZone[0],
    greenTo: greenZone[1],
    minorTicks: 5,
    min,
    max
  };

  const chartRef = useGoogleChart({
    chartType: 'Gauge',
    data: chartData,
    options,
    packages: ['gauge']
  });

  return <div ref={chartRef} className="gauge-chart" />;
};

// Multi-Gauge Dashboard Component
export const KPIDashboard: React.FC = () => {
  const kpis = [
    { label: "NPS", value: 72, redZone: [0, 30], yellowZone: [30, 70], greenZone: [70, 100] },
    { label: "CSAT", value: 8.2, min: 0, max: 10, redZone: [0, 5], yellowZone: [5, 7], greenZone: [7, 10] },
    { label: "Response Rate", value: 85, redZone: [0, 40], yellowZone: [40, 70], greenZone: [70, 100] }
  ];

  return (
    <div className="kpi-dashboard" style={{ display: 'flex', gap: '20px' }}>
      {kpis.map((kpi, index) => (
        <GaugeChart key={index} {...kpi} />
      ))}
    </div>
  );
};
```

### GeoChart Component
```tsx
// components/GeoChart.tsx
import React from 'react';
import { useGoogleChart } from '../hooks/useGoogleChart';

interface GeoChartData {
  location: string;
  value: number;
}

interface GeoChartProps {
  data: GeoChartData[];
  title?: string;
  region?: string;
  displayMode?: 'regions' | 'markers' | 'text';
  colorAxis?: {
    minValue: number;
    maxValue: number;
    colors: string[];
  };
  width?: number;
  height?: number;
}

export const GeoChart: React.FC<GeoChartProps> = ({
  data,
  title = "Geographic Data",
  region = "US",
  displayMode = "regions",
  colorAxis = {
    minValue: 0,
    maxValue: 100,
    colors: ['#FF6B6B', '#FFE66D', '#4ECDC4', '#45B7D1']
  },
  width = 900,
  height = 500
}) => {
  const chartData = [
    ['Location', 'Value'],
    ...data.map(item => [item.location, item.value])
  ];

  const options = {
    title,
    region,
    displayMode,
    resolution: region === 'US' ? 'provinces' : 'countries',
    width,
    height,
    colorAxis,
    backgroundColor: '#f5f5f5',
    datalessRegionColor: '#E8E8E8'
  };

  const chartRef = useGoogleChart({
    chartType: 'GeoChart',
    data: chartData,
    options,
    packages: ['geochart']
  });

  return <div ref={chartRef} className="geo-chart" />;
};

// Usage with state data
const RegionalAnalysis: React.FC = () => {
  const stateData = [
    { location: "US-CA", value: 75 },
    { location: "US-TX", value: 68 },
    { location: "US-NY", value: 72 },
    { location: "US-FL", value: 65 }
  ];

  return (
    <GeoChart 
      data={stateData}
      title="NPS Score by State"
      region="US"
      colorAxis={{
        minValue: 50,
        maxValue: 80,
        colors: ['#e74c3c', '#f39c12', '#f1c40f', '#2ecc71']
      }}
    />
  );
};
```

## Advanced Patterns

### Chart with Loading State
```tsx
// components/ChartWithLoading.tsx
import React, { useState, useEffect } from 'react';
import { ComboChart } from './ComboChart';

interface ChartWithLoadingProps {
  dataUrl: string;
}

export const ChartWithLoading: React.FC<ChartWithLoadingProps> = ({ dataUrl }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const response = await fetch(dataUrl);
        const result = await response.json();
        setData(result);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [dataUrl]);

  if (loading) {
    return (
      <div className="chart-loading">
        <div className="spinner">Loading chart...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="chart-error">
        <p>Error loading chart: {error}</p>
      </div>
    );
  }

  return <ComboChart data={data} />;
};
```

### Interactive Chart with Events
```tsx
// components/InteractiveChart.tsx
import React, { useCallback } from 'react';
import { useGoogleChart } from '../hooks/useGoogleChart';

export const InteractiveChart: React.FC<{ data: any[] }> = ({ data }) => {
  const handleChartSelect = useCallback((chart: any) => {
    google.visualization.events.addListener(chart, 'select', () => {
      const selection = chart.getSelection();
      if (selection.length > 0) {
        const row = selection[0].row;
        const category = data[row + 1][0]; // +1 because of header
        const value = data[row + 1][1];
        console.log(`Selected: ${category} - ${value}`);
        
        // Trigger custom event or callback
        onSelectionChange?.(category, value);
      }
    });
  }, [data]);

  const chartRef = useGoogleChart({
    chartType: 'ColumnChart',
    data,
    options: { title: 'Interactive Chart' },
    onChartReady: handleChartSelect
  });

  return <div ref={chartRef} />;
};
```

## Context Provider for Charts

### Chart Configuration Context
```tsx
// context/ChartContext.tsx
import React, { createContext, useContext, ReactNode } from 'react';

interface ChartConfig {
  theme: 'light' | 'dark';
  colorScheme: string[];
  defaultWidth: number;
  defaultHeight: number;
}

interface ChartContextType {
  config: ChartConfig;
  updateConfig: (config: Partial<ChartConfig>) => void;
}

const ChartContext = createContext<ChartContextType | undefined>(undefined);

export const ChartProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [config, setConfig] = useState<ChartConfig>({
    theme: 'light',
    colorScheme: ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728'],
    defaultWidth: 800,
    defaultHeight: 400
  });

  const updateConfig = (newConfig: Partial<ChartConfig>) => {
    setConfig(prev => ({ ...prev, ...newConfig }));
  };

  return (
    <ChartContext.Provider value={{ config, updateConfig }}>
      {children}
    </ChartContext.Provider>
  );
};

export const useChartConfig = () => {
  const context = useContext(ChartContext);
  if (!context) {
    throw new Error('useChartConfig must be used within ChartProvider');
  }
  return context;
};
```

## Custom Hooks

### Data Transformation Hook
```tsx
// hooks/useChartData.ts
import { useMemo } from 'react';
import { UniversalChartData } from '../types/chartTypes';

export const useChartData = (universalData: UniversalChartData) => {
  return useMemo(() => {
    switch (universalData.type) {
      case 'combo':
        return [
          ['Category', 'Volume', 'Score'],
          ...universalData.labels.map((label, index) => [
            label,
            universalData.datasets[0]?.data[index]?.y || 0,
            universalData.datasets[1]?.data[index]?.y || 0
          ])
        ];
      
      case 'gauge':
        return [
          ['Label', 'Value'],
          ['Current', universalData.gauge_value]
        ];
      
      case 'geo':
        return [
          ['Location', 'Value'],
          ...universalData.geographic_data.map(item => [
            item.location,
            item.value
          ])
        ];
      
      default:
        return [];
    }
  }, [universalData]);
};
```

### Real-time Updates Hook
```tsx
// hooks/useRealTimeChart.ts
import { useState, useEffect } from 'react';

export const useRealTimeChart = (endpoint: string, interval: number = 30000) => {
  const [data, setData] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(new Date());

  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await fetch(endpoint);
        const newData = await response.json();
        setData(newData);
        setLastUpdate(new Date());
      } catch (error) {
        console.error('Failed to fetch real-time data:', error);
      }
    };

    // Initial fetch
    fetchData();

    // Set up interval
    const intervalId = setInterval(fetchData, interval);

    return () => clearInterval(intervalId);
  }, [endpoint, interval]);

  return { data, lastUpdate };
};
```

## TypeScript Definitions

### Chart Types
```tsx
// types/chartTypes.ts
export interface ChartDataPoint {
  x?: string | number;
  y?: number;
  value?: number;
  label?: string;
  category?: string;
}

export interface ChartDataset {
  label: string;
  data: ChartDataPoint[];
  backgroundColor?: string[];
  borderColor?: string[];
  yAxisId?: string;
  xAxisId?: string;
}

export interface UniversalChartData {
  type: string;
  title?: string;
  datasets: ChartDataset[];
  labels?: string[];
  xAxisLabel?: string;
  yAxisLabel?: string;
  gauge_value?: number;
  gauge_min?: number;
  gauge_max?: number;
  geographic_data?: Array<{
    location: string;
    value: number;
  }>;
}

// Extend window object for Google Charts
declare global {
  interface Window {
    google: {
      charts: {
        load: (version: string, options: any) => void;
        setOnLoadCallback: (callback: () => void) => void;
      };
      visualization: {
        arrayToDataTable: (data: any[][]) => any;
        DataTable: new () => any;
        ComboChart: new (element: HTMLElement) => any;
        Gauge: new (element: HTMLElement) => any;
        GeoChart: new (element: HTMLElement) => any;
        events: {
          addListener: (chart: any, event: string, callback: () => void) => void;
        };
      };
    };
  }
}
```

## Best Practices

### Performance Optimization
```tsx
// Memoize chart components
const MemoizedComboChart = React.memo(ComboChart);

// Use callback refs for better performance
const useChartRef = () => {
  return useCallback((node: HTMLDivElement | null) => {
    if (node) {
      // Chart initialization logic
    }
  }, []);
};

// Debounce data updates
import { useDebouncedCallback } from 'use-debounce';

const debouncedUpdate = useDebouncedCallback(
  (newData) => {
    updateChart(newData);
  },
  300
);
```

### Error Boundaries
```tsx
// components/ChartErrorBoundary.tsx
import React, { Component, ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error?: Error;
}

export class ChartErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: any) {
    console.error('Chart error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="chart-error">
          <h3>Chart Error</h3>
          <p>Unable to render chart. Please try refreshing.</p>
          <details>
            <summary>Error Details</summary>
            <pre>{this.state.error?.message}</pre>
          </details>
        </div>
      );
    }

    return this.props.children;
  }
}
```

## Testing

### Jest Testing
```tsx
// __tests__/ComboChart.test.tsx
import React from 'react';
import { render, screen } from '@testing-library/react';
import { ComboChart } from '../components/ComboChart';

// Mock Google Charts
const mockGoogle = {
  charts: {
    load: jest.fn(),
    setOnLoadCallback: jest.fn()
  },
  visualization: {
    arrayToDataTable: jest.fn(),
    ComboChart: jest.fn(() => ({
      draw: jest.fn()
    }))
  }
};

(global as any).google = mockGoogle;

describe('ComboChart', () => {
  const mockData = [
    { category: "Test", volume: 100, score: 75 }
  ];

  it('renders without crashing', () => {
    render(<ComboChart data={mockData} />);
    expect(screen.getByRole('generic')).toBeInTheDocument();
  });

  it('calls Google Charts with correct data', () => {
    render(<ComboChart data={mockData} title="Test Chart" />);
    
    expect(mockGoogle.visualization.arrayToDataTable).toHaveBeenCalledWith([
      ['Category', 'Volume', 'Score'],
      ['Test', 100, 75]
    ]);
  });
});
```

This comprehensive React guide provides everything needed to implement Google Charts in React applications with TypeScript support, proper error handling, and performance optimization!
