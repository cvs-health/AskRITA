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
# Google Charts with Angular Framework

## Overview
Complete guide for integrating Google Charts with Angular applications, including TypeScript support, services, components, and best practices for survey data visualization.

## Installation & Setup

### Install Dependencies
```bash
# Core Angular dependencies (if not already installed)
ng new survey-dashboard
cd survey-dashboard

# TypeScript types for Google Charts
npm install -D @types/google.visualization

# Alternative: Use angular-google-charts wrapper
npm install angular-google-charts
```

### Load Google Charts Library
```typescript
// Method 1: Add to angular.json
"scripts": [
  "https://www.gstatic.com/charts/loader.js"
]

// Method 2: Add to index.html
<script type="text/javascript" src="https://www.gstatic.com/charts/loader.js"></script>

// Method 3: Dynamic loading service (recommended)
// services/google-charts.service.ts
import { Injectable } from '@angular/core';

@Injectable({
  providedIn: 'root'
})
export class GoogleChartsService {
  private isLoaded = false;
  private loadingPromise: Promise<void> | null = null;

  async loadGoogleCharts(): Promise<void> {
    if (this.isLoaded) {
      return Promise.resolve();
    }

    if (this.loadingPromise) {
      return this.loadingPromise;
    }

    this.loadingPromise = new Promise<void>((resolve, reject) => {
      if (typeof google !== 'undefined' && google.charts) {
        this.isLoaded = true;
        resolve();
        return;
      }

      const script = document.createElement('script');
      script.type = 'text/javascript';
      script.src = 'https://www.gstatic.com/charts/loader.js';
      script.onload = () => {
        google.charts.load('current', {
          packages: ['corechart', 'gauge', 'geochart', 'sankey', 'treemap', 'timeline', 'calendar', 'table']
        });
        google.charts.setOnLoadCallback(() => {
          this.isLoaded = true;
          resolve();
        });
      };
      script.onerror = () => reject(new Error('Failed to load Google Charts'));
      document.head.appendChild(script);
    });

    return this.loadingPromise;
  }

  isGoogleChartsLoaded(): boolean {
    return this.isLoaded;
  }
}
```

## Base Chart Service

### Chart Data Service
```typescript
// services/chart-data.service.ts
import { Injectable } from '@angular/core';
import { Observable, BehaviorSubject } from 'rxjs';
import { HttpClient } from '@angular/common/http';

export interface UniversalChartData {
  type: string;
  title?: string;
  datasets: ChartDataset[];
  labels?: string[];
  gauge_value?: number;
  gauge_min?: number;
  gauge_max?: number;
  geographic_data?: GeographicData[];
}

export interface ChartDataset {
  label: string;
  data: DataPoint[];
  yAxisId?: string;
}

export interface DataPoint {
  x?: string | number;
  y?: number;
  value?: number;
  category?: string;
}

export interface GeographicData {
  location: string;
  value: number;
}

@Injectable({
  providedIn: 'root'
})
export class ChartDataService {
  private dataSubject = new BehaviorSubject<UniversalChartData | null>(null);
  public data$ = this.dataSubject.asObservable();

  constructor(private http: HttpClient) {}

  async fetchSurveyData(endpoint: string): Promise<UniversalChartData> {
    try {
      const data = await this.http.get<UniversalChartData>(endpoint).toPromise();
      this.dataSubject.next(data);
      return data;
    } catch (error) {
      console.error('Error fetching survey data:', error);
      throw error;
    }
  }

  transformToGoogleChartsFormat(universalData: UniversalChartData): any[][] {
    switch (universalData.type) {
      case 'combo':
        return [
          ['Category', 'Volume', 'Score'],
          ...universalData.labels!.map((label, index) => [
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
          ...universalData.geographic_data!.map(item => [
            item.location,
            item.value
          ])
        ];
      
      default:
        return [];
    }
  }
}
```

## Chart Components

### Base Chart Component
```typescript
// components/base-chart/base-chart.component.ts
import { Component, ElementRef, Input, OnInit, OnDestroy, ViewChild, OnChanges, SimpleChanges } from '@angular/core';
import { GoogleChartsService } from '../../services/google-charts.service';

@Component({
  selector: 'app-base-chart',
  template: `
    <div #chartContainer class="chart-container" [style.width.px]="width" [style.height.px]="height">
      <div *ngIf="loading" class="loading-spinner">
        <mat-spinner diameter="40"></mat-spinner>
        <p>Loading chart...</p>
      </div>
      <div *ngIf="error" class="error-message">
        <mat-icon>error</mat-icon>
        <p>{{ error }}</p>
      </div>
    </div>
  `,
  styles: [`
    .chart-container {
      position: relative;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .loading-spinner, .error-message {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 10px;
    }
    .error-message {
      color: #f44336;
    }
  `]
})
export class BaseChartComponent implements OnInit, OnDestroy, OnChanges {
  @ViewChild('chartContainer', { static: true }) chartContainer!: ElementRef;
  
  @Input() chartType!: string;
  @Input() data: any[][] = [];
  @Input() options: any = {};
  @Input() width: number = 800;
  @Input() height: number = 400;
  @Input() packages: string[] = ['corechart'];

  loading = true;
  error: string | null = null;
  private chart: any;

  constructor(private googleChartsService: GoogleChartsService) {}

  async ngOnInit() {
    await this.initializeChart();
  }

  ngOnChanges(changes: SimpleChanges) {
    if ((changes['data'] || changes['options']) && this.chart) {
      this.drawChart();
    }
  }

  ngOnDestroy() {
    if (this.chart) {
      this.chart.clearChart?.();
    }
  }

  private async initializeChart() {
    try {
      this.loading = true;
      this.error = null;

      await this.googleChartsService.loadGoogleCharts();
      
      if (!google.visualization[this.chartType]) {
        throw new Error(`Chart type ${this.chartType} not supported`);
      }

      this.chart = new google.visualization[this.chartType](this.chartContainer.nativeElement);
      this.drawChart();
    } catch (error) {
      this.error = `Failed to initialize chart: ${error}`;
      console.error('Chart initialization error:', error);
    } finally {
      this.loading = false;
    }
  }

  private drawChart() {
    if (!this.chart || !this.data.length) return;

    try {
      const dataTable = google.visualization.arrayToDataTable(this.data);
      this.chart.draw(dataTable, this.options);
    } catch (error) {
      this.error = `Failed to draw chart: ${error}`;
      console.error('Chart drawing error:', error);
    }
  }

  public redraw() {
    this.drawChart();
  }
}
```

### ComboChart Component
```typescript
// components/combo-chart/combo-chart.component.ts
import { Component, Input, OnInit } from '@angular/core';

export interface ComboChartData {
  category: string;
  volume: number;
  score: number;
}

@Component({
  selector: 'app-combo-chart',
  template: `
    <div class="combo-chart-wrapper">
      <h3 *ngIf="title" class="chart-title">{{ title }}</h3>
      <app-base-chart
        chartType="ComboChart"
        [data]="chartData"
        [options]="chartOptions"
        [width]="width"
        [height]="height">
      </app-base-chart>
    </div>
  `,
  styles: [`
    .combo-chart-wrapper {
      padding: 16px;
      border-radius: 8px;
      box-shadow: 0 2px 4px rgba(0,0,0,0.1);
      background: white;
    }
    .chart-title {
      text-align: center;
      margin-bottom: 16px;
      color: #333;
    }
  `]
})
export class ComboChartComponent implements OnInit {
  @Input() data: ComboChartData[] = [];
  @Input() title: string = '';
  @Input() width: number = 900;
  @Input() height: number = 500;
  @Input() volumeLabel: string = 'Volume';
  @Input() scoreLabel: string = 'Score';

  chartData: any[][] = [];
  chartOptions: any = {};

  ngOnInit() {
    this.updateChartData();
    this.updateChartOptions();
  }

  ngOnChanges() {
    this.updateChartData();
    this.updateChartOptions();
  }

  private updateChartData() {
    this.chartData = [
      ['Category', this.volumeLabel, this.scoreLabel],
      ...this.data.map(item => [item.category, item.volume, item.score])
    ];
  }

  private updateChartOptions() {
    this.chartOptions = {
      title: this.title,
      width: this.width,
      height: this.height,
      vAxes: {
        0: {
          title: this.volumeLabel,
          textStyle: { color: '#1f77b4' },
          titleTextStyle: { color: '#1f77b4' },
          format: '#,###'
        },
        1: {
          title: this.scoreLabel,
          textStyle: { color: '#ff7f0e' },
          titleTextStyle: { color: '#ff7f0e' },
          minValue: 0,
          maxValue: 100
        }
      },
      series: {
        0: { type: 'columns', targetAxisIndex: 0, color: '#1f77b4' },
        1: { type: 'line', targetAxisIndex: 1, color: '#ff7f0e', lineWidth: 3, pointSize: 8 }
      },
      legend: { position: 'top', alignment: 'center' },
      chartArea: { left: 80, top: 80, width: '75%', height: '70%' }
    };
  }
}

// combo-chart.component.html (alternative template approach)
/*
<div class="combo-chart-container">
  <mat-card>
    <mat-card-header>
      <mat-card-title>{{ title }}</mat-card-title>
    </mat-card-header>
    <mat-card-content>
      <app-base-chart
        chartType="ComboChart"
        [data]="chartData"
        [options]="chartOptions"
        [width]="width"
        [height]="height">
      </app-base-chart>
    </mat-card-content>
  </mat-card>
</div>
*/
```

### Gauge Component
```typescript
// components/gauge-chart/gauge-chart.component.ts
import { Component, Input, OnInit } from '@angular/core';

@Component({
  selector: 'app-gauge-chart',
  template: `
    <div class="gauge-chart-wrapper">
      <h4 *ngIf="label" class="gauge-label">{{ label }}</h4>
      <app-base-chart
        chartType="Gauge"
        [data]="chartData"
        [options]="chartOptions"
        [width]="width"
        [height]="height"
        [packages]="['gauge']">
      </app-base-chart>
      <div class="gauge-value">{{ value }}</div>
    </div>
  `,
  styles: [`
    .gauge-chart-wrapper {
      text-align: center;
      padding: 16px;
      border-radius: 8px;
      background: white;
      box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .gauge-label {
      margin-bottom: 8px;
      color: #333;
      font-weight: 500;
    }
    .gauge-value {
      font-size: 24px;
      font-weight: bold;
      color: #333;
      margin-top: 8px;
    }
  `]
})
export class GaugeChartComponent implements OnInit {
  @Input() value: number = 0;
  @Input() label: string = '';
  @Input() min: number = 0;
  @Input() max: number = 100;
  @Input() redZone: [number, number] = [0, 30];
  @Input() yellowZone: [number, number] = [30, 70];
  @Input() greenZone: [number, number] = [70, 100];
  @Input() width: number = 400;
  @Input() height: number = 300;

  chartData: any[][] = [];
  chartOptions: any = {};

  ngOnInit() {
    this.updateChartData();
    this.updateChartOptions();
  }

  ngOnChanges() {
    this.updateChartData();
    this.updateChartOptions();
  }

  private updateChartData() {
    this.chartData = [
      ['Label', 'Value'],
      [this.label, this.value]
    ];
  }

  private updateChartOptions() {
    this.chartOptions = {
      width: this.width,
      height: this.height,
      redFrom: this.redZone[0],
      redTo: this.redZone[1],
      yellowFrom: this.yellowZone[0],
      yellowTo: this.yellowZone[1],
      greenFrom: this.greenZone[0],
      greenTo: this.greenZone[1],
      minorTicks: 5,
      min: this.min,
      max: this.max
    };
  }
}

// KPI Dashboard Component
@Component({
  selector: 'app-kpi-dashboard',
  template: `
    <div class="kpi-dashboard">
      <h2>Key Performance Indicators</h2>
      <div class="kpi-grid">
        <app-gauge-chart
          *ngFor="let kpi of kpis"
          [value]="kpi.value"
          [label]="kpi.label"
          [min]="kpi.min"
          [max]="kpi.max"
          [redZone]="kpi.redZone"
          [yellowZone]="kpi.yellowZone"
          [greenZone]="kpi.greenZone">
        </app-gauge-chart>
      </div>
    </div>
  `,
  styles: [`
    .kpi-dashboard {
      padding: 24px;
    }
    .kpi-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
      gap: 24px;
      margin-top: 24px;
    }
  `]
})
export class KpiDashboardComponent {
  kpis = [
    {
      label: 'NPS Score',
      value: 72,
      min: 0,
      max: 100,
      redZone: [0, 30] as [number, number],
      yellowZone: [30, 70] as [number, number],
      greenZone: [70, 100] as [number, number]
    },
    {
      label: 'CSAT Score',
      value: 8.2,
      min: 0,
      max: 10,
      redZone: [0, 5] as [number, number],
      yellowZone: [5, 7] as [number, number],
      greenZone: [7, 10] as [number, number]
    },
    {
      label: 'Response Rate',
      value: 85,
      min: 0,
      max: 100,
      redZone: [0, 40] as [number, number],
      yellowZone: [40, 70] as [number, number],
      greenZone: [70, 100] as [number, number]
    }
  ];
}
```

### GeoChart Component
```typescript
// components/geo-chart/geo-chart.component.ts
import { Component, Input, OnInit } from '@angular/core';

export interface GeoChartData {
  location: string;
  value: number;
}

@Component({
  selector: 'app-geo-chart',
  template: `
    <div class="geo-chart-wrapper">
      <h3 *ngIf="title" class="chart-title">{{ title }}</h3>
      <app-base-chart
        chartType="GeoChart"
        [data]="chartData"
        [options]="chartOptions"
        [width]="width"
        [height]="height"
        [packages]="['geochart']">
      </app-base-chart>
      <div class="geo-legend" *ngIf="showLegend">
        <div class="legend-item" *ngFor="let item of legendItems">
          <div class="legend-color" [style.background-color]="item.color"></div>
          <span>{{ item.label }}</span>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .geo-chart-wrapper {
      padding: 16px;
      border-radius: 8px;
      background: white;
      box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .chart-title {
      text-align: center;
      margin-bottom: 16px;
      color: #333;
    }
    .geo-legend {
      display: flex;
      justify-content: center;
      gap: 16px;
      margin-top: 16px;
    }
    .legend-item {
      display: flex;
      align-items: center;
      gap: 4px;
    }
    .legend-color {
      width: 16px;
      height: 16px;
      border-radius: 2px;
    }
  `]
})
export class GeoChartComponent implements OnInit {
  @Input() data: GeoChartData[] = [];
  @Input() title: string = '';
  @Input() region: string = 'US';
  @Input() displayMode: 'regions' | 'markers' | 'text' = 'regions';
  @Input() width: number = 900;
  @Input() height: number = 500;
  @Input() showLegend: boolean = true;
  @Input() colorAxis = {
    minValue: 0,
    maxValue: 100,
    colors: ['#FF6B6B', '#FFE66D', '#4ECDC4', '#45B7D1']
  };

  chartData: any[][] = [];
  chartOptions: any = {};
  legendItems: { color: string; label: string }[] = [];

  ngOnInit() {
    this.updateChartData();
    this.updateChartOptions();
    this.updateLegend();
  }

  ngOnChanges() {
    this.updateChartData();
    this.updateChartOptions();
    this.updateLegend();
  }

  private updateChartData() {
    this.chartData = [
      ['Location', 'Value'],
      ...this.data.map(item => [item.location, item.value])
    ];
  }

  private updateChartOptions() {
    this.chartOptions = {
      title: this.title,
      region: this.region,
      displayMode: this.displayMode,
      resolution: this.region === 'US' ? 'provinces' : 'countries',
      width: this.width,
      height: this.height,
      colorAxis: this.colorAxis,
      backgroundColor: '#f5f5f5',
      datalessRegionColor: '#E8E8E8'
    };
  }

  private updateLegend() {
    if (!this.showLegend) return;
    
    this.legendItems = [
      { color: this.colorAxis.colors[0], label: `${this.colorAxis.minValue} - Low` },
      { color: this.colorAxis.colors[1], label: 'Medium-Low' },
      { color: this.colorAxis.colors[2], label: 'Medium-High' },
      { color: this.colorAxis.colors[3], label: `High - ${this.colorAxis.maxValue}` }
    ];
  }
}
```

## Advanced Features

### Real-time Data Service
```typescript
// services/real-time-data.service.ts
import { Injectable } from '@angular/core';
import { Observable, interval, switchMap } from 'rxjs';
import { HttpClient } from '@angular/common/http';
import { WebSocketSubject } from 'rxjs/webSocket';

@Injectable({
  providedIn: 'root'
})
export class RealTimeDataService {
  private wsSubject?: WebSocketSubject<any>;

  constructor(private http: HttpClient) {}

  // Polling approach
  getPollingData(endpoint: string, intervalMs: number = 30000): Observable<any> {
    return interval(intervalMs).pipe(
      switchMap(() => this.http.get(endpoint))
    );
  }

  // WebSocket approach
  getWebSocketData(wsUrl: string): Observable<any> {
    if (!this.wsSubject) {
      this.wsSubject = new WebSocketSubject(wsUrl);
    }
    return this.wsSubject.asObservable();
  }

  sendWebSocketMessage(message: any) {
    if (this.wsSubject) {
      this.wsSubject.next(message);
    }
  }

  closeWebSocket() {
    if (this.wsSubject) {
      this.wsSubject.complete();
      this.wsSubject = undefined;
    }
  }
}
```

### Interactive Chart Directive
```typescript
// directives/chart-interactions.directive.ts
import { Directive, ElementRef, Output, EventEmitter, OnInit, OnDestroy } from '@angular/core';

@Directive({
  selector: '[appChartInteractions]'
})
export class ChartInteractionsDirective implements OnInit, OnDestroy {
  @Output() chartSelect = new EventEmitter<any>();
  @Output() chartReady = new EventEmitter<any>();
  @Output() chartError = new EventEmitter<any>();

  private chart: any;
  private listeners: any[] = [];

  constructor(private el: ElementRef) {}

  ngOnInit() {
    // Wait for chart to be initialized
    setTimeout(() => {
      this.setupInteractions();
    }, 1000);
  }

  ngOnDestroy() {
    this.removeListeners();
  }

  private setupInteractions() {
    // Find chart instance (implementation depends on your chart setup)
    const chartElement = this.el.nativeElement.querySelector('.google-visualization-chart');
    if (!chartElement) return;

    // Add event listeners
    if (google && google.visualization && google.visualization.events) {
      this.listeners.push(
        google.visualization.events.addListener(this.chart, 'select', () => {
          const selection = this.chart.getSelection();
          this.chartSelect.emit(selection);
        })
      );

      this.listeners.push(
        google.visualization.events.addListener(this.chart, 'ready', () => {
          this.chartReady.emit(this.chart);
        })
      );

      this.listeners.push(
        google.visualization.events.addListener(this.chart, 'error', (error: any) => {
          this.chartError.emit(error);
        })
      );
    }
  }

  private removeListeners() {
    if (google && google.visualization && google.visualization.events) {
      this.listeners.forEach(listener => {
        google.visualization.events.removeListener(listener);
      });
    }
    this.listeners = [];
  }
}
```

## Module Setup

### Charts Module
```typescript
// modules/charts.module.ts
import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClientModule } from '@angular/common/http';
import { MatCardModule } from '@angular/material/card';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatIconModule } from '@angular/material/icon';

import { BaseChartComponent } from '../components/base-chart/base-chart.component';
import { ComboChartComponent } from '../components/combo-chart/combo-chart.component';
import { GaugeChartComponent } from '../components/gauge-chart/gauge-chart.component';
import { GeoChartComponent } from '../components/geo-chart/geo-chart.component';
import { KpiDashboardComponent } from '../components/kpi-dashboard/kpi-dashboard.component';

import { ChartInteractionsDirective } from '../directives/chart-interactions.directive';

import { GoogleChartsService } from '../services/google-charts.service';
import { ChartDataService } from '../services/chart-data.service';
import { RealTimeDataService } from '../services/real-time-data.service';

@NgModule({
  declarations: [
    BaseChartComponent,
    ComboChartComponent,
    GaugeChartComponent,
    GeoChartComponent,
    KpiDashboardComponent,
    ChartInteractionsDirective
  ],
  imports: [
    CommonModule,
    HttpClientModule,
    MatCardModule,
    MatProgressSpinnerModule,
    MatIconModule
  ],
  providers: [
    GoogleChartsService,
    ChartDataService,
    RealTimeDataService
  ],
  exports: [
    BaseChartComponent,
    ComboChartComponent,
    GaugeChartComponent,
    GeoChartComponent,
    KpiDashboardComponent,
    ChartInteractionsDirective
  ]
})
export class ChartsModule { }
```

## Dashboard Implementation

### Survey Dashboard Component
```typescript
// components/survey-dashboard/survey-dashboard.component.ts
import { Component, OnInit, OnDestroy } from '@angular/core';
import { Subject, takeUntil } from 'rxjs';
import { ChartDataService } from '../../services/chart-data.service';
import { RealTimeDataService } from '../../services/real-time-data.service';

@Component({
  selector: 'app-survey-dashboard',
  template: `
    <div class="dashboard-container">
      <header class="dashboard-header">
        <h1>Survey Analytics Dashboard</h1>
        <div class="last-updated">
          Last Updated: {{ lastUpdated | date:'medium' }}
        </div>
      </header>

      <div class="dashboard-grid">
        <!-- KPI Gauges -->
        <div class="kpi-section">
          <app-kpi-dashboard></app-kpi-dashboard>
        </div>

        <!-- Response Volume vs NPS -->
        <div class="combo-section">
          <app-combo-chart
            [data]="comboData"
            title="Response Volume vs NPS Score by Segment"
            volumeLabel="Response Count"
            scoreLabel="NPS Score">
          </app-combo-chart>
        </div>

        <!-- Geographic Analysis -->
        <div class="geo-section">
          <app-geo-chart
            [data]="geoData"
            title="Regional Satisfaction Scores"
            region="US"
            [colorAxis]="geoColorAxis">
          </app-geo-chart>
        </div>

        <!-- Filters and Controls -->
        <div class="controls-section">
          <mat-card>
            <mat-card-header>
              <mat-card-title>Filters</mat-card-title>
            </mat-card-header>
            <mat-card-content>
              <mat-form-field>
                <mat-label>Date Range</mat-label>
                <mat-date-range-input [rangePicker]="picker">
                  <input matStartDate placeholder="Start date">
                  <input matEndDate placeholder="End date">
                </mat-date-range-input>
                <mat-datepicker-toggle matSuffix [for]="picker"></mat-datepicker-toggle>
                <mat-date-range-picker #picker></mat-date-range-picker>
              </mat-form-field>

              <mat-form-field>
                <mat-label>Business Segment</mat-label>
                <mat-select [(value)]="selectedSegment" (selectionChange)="onSegmentChange($event)">
                  <mat-option value="all">All Segments</mat-option>
                  <mat-option value="commercial">Commercial</mat-option>
                  <mat-option value="medicare">Medicare</mat-option>
                  <mat-option value="medicaid">Medicaid</mat-option>
                </mat-select>
              </mat-form-field>
            </mat-card-content>
          </mat-card>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .dashboard-container {
      padding: 24px;
      background: #f5f5f5;
      min-height: 100vh;
    }
    .dashboard-header {
      text-align: center;
      margin-bottom: 32px;
    }
    .dashboard-header h1 {
      margin: 0;
      color: #333;
    }
    .last-updated {
      color: #666;
      font-size: 14px;
      margin-top: 8px;
    }
    .dashboard-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      grid-template-rows: auto auto auto;
      gap: 24px;
    }
    .kpi-section {
      grid-column: 1 / -1;
    }
    .combo-section, .geo-section {
      grid-column: 1 / -1;
    }
    .controls-section {
      grid-column: 1 / -1;
    }
    @media (max-width: 768px) {
      .dashboard-grid {
        grid-template-columns: 1fr;
      }
    }
  `]
})
export class SurveyDashboardComponent implements OnInit, OnDestroy {
  private destroy$ = new Subject<void>();
  
  lastUpdated = new Date();
  selectedSegment = 'all';
  
  comboData = [
    { category: "Commercial", volume: 15420, score: 72 },
    { category: "Medicare", volume: 8932, score: 68 },
    { category: "Medicaid", volume: 5621, score: 45 },
    { category: "Individual", volume: 2103, score: 38 }
  ];

  geoData = [
    { location: "US-CA", value: 75 },
    { location: "US-TX", value: 68 },
    { location: "US-NY", value: 72 },
    { location: "US-FL", value: 65 }
  ];

  geoColorAxis = {
    minValue: 50,
    maxValue: 80,
    colors: ['#e74c3c', '#f39c12', '#f1c40f', '#2ecc71']
  };

  constructor(
    private chartDataService: ChartDataService,
    private realTimeDataService: RealTimeDataService
  ) {}

  ngOnInit() {
    this.setupRealTimeUpdates();
    this.loadInitialData();
  }

  ngOnDestroy() {
    this.destroy$.next();
    this.destroy$.complete();
  }

  private setupRealTimeUpdates() {
    // Poll for updates every 30 seconds
    this.realTimeDataService.getPollingData('/api/survey-data', 30000)
      .pipe(takeUntil(this.destroy$))
      .subscribe(data => {
        this.updateChartData(data);
        this.lastUpdated = new Date();
      });
  }

  private async loadInitialData() {
    try {
      const data = await this.chartDataService.fetchSurveyData('/api/survey-data');
      this.updateChartData(data);
    } catch (error) {
      console.error('Failed to load initial data:', error);
    }
  }

  private updateChartData(data: any) {
    // Update chart data based on received data
    if (data.comboData) {
      this.comboData = data.comboData;
    }
    if (data.geoData) {
      this.geoData = data.geoData;
    }
  }

  onSegmentChange(event: any) {
    // Filter data based on selected segment
    this.loadDataForSegment(event.value);
  }

  private loadDataForSegment(segment: string) {
    // Implementation for filtering data by segment
    console.log('Loading data for segment:', segment);
  }
}
```

## Testing

### Unit Testing
```typescript
// components/combo-chart/combo-chart.component.spec.ts
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ComboChartComponent } from './combo-chart.component';
import { GoogleChartsService } from '../../services/google-charts.service';

describe('ComboChartComponent', () => {
  let component: ComboChartComponent;
  let fixture: ComponentFixture<ComboChartComponent>;
  let mockGoogleChartsService: jasmine.SpyObj<GoogleChartsService>;

  beforeEach(async () => {
    const spy = jasmine.createSpyObj('GoogleChartsService', ['loadGoogleCharts', 'isGoogleChartsLoaded']);

    await TestBed.configureTestingModule({
      declarations: [ComboChartComponent],
      providers: [
        { provide: GoogleChartsService, useValue: spy }
      ]
    }).compileComponents();

    mockGoogleChartsService = TestBed.inject(GoogleChartsService) as jasmine.SpyObj<GoogleChartsService>;
  });

  beforeEach(() => {
    fixture = TestBed.createComponent(ComboChartComponent);
    component = fixture.componentInstance;
    
    // Mock Google Charts
    (window as any).google = {
      visualization: {
        arrayToDataTable: jasmine.createSpy('arrayToDataTable'),
        ComboChart: jasmine.createSpy('ComboChart').and.returnValue({
          draw: jasmine.createSpy('draw')
        })
      }
    };
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should transform data correctly', () => {
    const testData = [
      { category: 'Test', volume: 100, score: 75 }
    ];
    component.data = testData;
    component.ngOnInit();

    expect(component.chartData).toEqual([
      ['Category', 'Volume', 'Score'],
      ['Test', 100, 75]
    ]);
  });

  it('should update chart options when inputs change', () => {
    component.title = 'Test Chart';
    component.volumeLabel = 'Test Volume';
    component.scoreLabel = 'Test Score';
    
    component.ngOnInit();

    expect(component.chartOptions.title).toBe('Test Chart');
    expect(component.chartOptions.vAxes[0].title).toBe('Test Volume');
    expect(component.chartOptions.vAxes[1].title).toBe('Test Score');
  });
});
```

This comprehensive Angular guide provides everything needed to implement Google Charts in Angular applications with proper service architecture, component patterns, and testing strategies!
