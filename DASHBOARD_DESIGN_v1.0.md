# 📊 Agentic-Eco-Sentinel Dashboard - Design Specification v1.0

**Dashboard Name**: Agentic-Eco-Sentinel  
**Project**: AGENTIC_AI_POC_Phase3_1  
**Branch**: integration/dashboard-v1.0  
**Date**: June 23, 2026  
**Purpose**: Professional device monitoring, health tracking, and maintenance operations dashboard  
**Focus**: Client-centric (device monitoring, recommendations, maintenance) - No agent/MCP internals  

---

## 1. Dashboard Title & Branding

**Dashboard Name**: **Agentic-Eco-Sentinel Dashboard**

Branding Details:
- **Full Name**: Agentic-Eco-Sentinel Dashboard
- **Short Name**: Agentic-Eco-Sentinel
- **Acronym**: AES
- **Tagline**: "Intelligent Predictive Maintenance Platform"

Implementation:
- HTML `<title>` tag: `Agentic-Eco-Sentinel Dashboard`
- Page header (`<h1>`): `Agentic-Eco-Sentinel Dashboard`
- Browser tab name: `AES Dashboard`
- Logo area: "AES" initials or full branding
- Documentation: All references use "Agentic-Eco-Sentinel"

---

## 2. Professional Color Scheme

### Primary Colors
```
├── Deep Navy Blue: #1a2d4d (Headers, primary text, strong elements)
├── Slate Gray: #475569 (Secondary text, borders, subtle elements)
├── Off-White Background: #f8fafc (Main background)
└── White Cards: #ffffff (Card backgrounds)
```

### Semantic Colors
```
├── Healthy (Success): #10b981 (Emerald Green)
├── Warning (Attention): #f59e0b (Amber/Gold)
├── Critical (Urgent): #dc2626 (Crimson Red)
├── Informational: #0ea5e9 (Sky Blue)
├── Teal Accent: #0d9488 (Highlights, active states, CTAs)
└── Purple Secondary: #8b5cf6 (Future features)
```

### Text Colors
```
├── Primary Text: #1a2d4d (High contrast, body text)
├── Secondary Text: #64748b (Labels, descriptions)
└── Muted Text: #cbd5e1 (Placeholders, disabled elements)
```

---

## 3. Page Structure & Layout

### Overall Page Layout

```
┌─────────────────────────────────────────────────────────────────┐
│                          HEADER BAR                              │
│  Logo | Dashboard Title | Search | Refresh | Settings | Help    │
│  (Background: #1a2d4d - Deep Navy, Height: 70px)               │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    STICKY KPI CARDS ROW                          │
│  ┌──────────────┬──────────────┬──────────────┬──────────────┐  │
│  │  Fleet       │ Warning      │ Critical     │ Up-to-Date   │  │
│  │  Health      │ Devices      │ Devices      │ Maintenance  │  │
│  │  87%         │ 12           │ 3            │ 156/201      │  │
│  │  ████████░   │ ⚠            │ ✗            │ ✓            │  │
│  └──────────────┴──────────────┴──────────────┴──────────────┘  │
│  (Background: #f8fafc with borders, Padding: 16px)              │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                       TAB NAVIGATION                             │
│  [Overview] [Devices] [Maintenance] [Analytics] [Alerts]        │
│  (Underline animation on active tab, Color: #0d9488)           │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    DYNAMIC TAB CONTENT                           │
│  (Changes based on selected tab, min-height: 600px)             │
│                                                                 │
│  [Tab content renders here with full width]                    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                      FOOTER (Optional)                           │
│  Last updated: June 23, 2026, 3:45 PM | Auto-refresh: Every 5m  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. TAB 1: OVERVIEW (Fleet Dashboard Home)

**Purpose**: Quick view of fleet health and immediate action items

**Layout**: 2-Column grid with varied heights

### Left Column (60% width)

#### Section 1.1: Fleet Health Gauge (Top - 200px height)
```
┌─────────────────────────────────────────┐
│        FLEET HEALTH GAUGE               │
│  ┌─────────────────────────────────┐   │
│  │                                 │   │
│  │         87%                     │   │
│  │      ╭────────╮                │   │
│  │      │ HEALTHY│ ← Circular      │   │
│  │      ╰────────╯    gauge with   │   │
│  │    Excellent       segments     │   │
│  │    (Status color)               │   │
│  │                                 │   │
│  └─────────────────────────────────┘   │
│  Chart Type: Radial/Circular Progress   │
│  Animation: Smooth percentage fill      │
│  Gauge Segments:                        │
│    - 0-50%: Red (#dc2626)              │
│    - 51-75%: Amber (#f59e0b)           │
│    - 76-100%: Green (#10b981)          │
└─────────────────────────────────────────┘
```

#### Section 1.2: Device Status Distribution (Middle - 300px height)
```
┌─────────────────────────────────────────┐
│   STATUS DISTRIBUTION PIE/DONUT         │
│  ┌─────────────────────────────────┐   │
│  │                                 │   │
│  │  Healthy: 175 (87%)            │   │
│  │  Warning: 12   (6%)            │   │
│  │  Critical: 3   (1%)            │   │
│  │  Pending:  11  (6%)            │   │
│  │  ┌─────────────────────────────┐   │
│  │  │ [Pie/Donut Chart]           │   │
│  │  │ - Colors per status type    │   │
│  │  │ - Interactive legend        │   │
│  │  │ - Click to filter device list│   │
│  │  └─────────────────────────────┘   │
│  │                                 │   │
│  └─────────────────────────────────┘   │
└─────────────────────────────────────────┘
```

#### Section 1.3: 7-Day Trend Line Chart (Bottom - 250px height)
```
┌─────────────────────────────────────────┐
│    FLEET HEALTH TREND (Last 7 Days)     │
│  ┌─────────────────────────────────┐   │
│  │ 100%│                           │   │
│  │     │    ╱╲ ╱╲                  │   │
│  │  80%│   ╱  ╲╱  ╲                │   │
│  │     │  ╱         ╲              │   │
│  │  60%│ ╱           ╲             │   │
│  │     │╱─────────────╲───────     │   │
│  │  40%└──────────────────         │   │
│  │   0%                            │   │
│  │   M  T  W  T  F  S  S          │   │
│  │                                 │   │
│  │ Line Color: #0d9488 (Teal)     │   │
│  │ Fill Area: Gradient background  │   │
│  │ Animation: Smooth line drawing  │   │
│  │ Hover: Tooltip with exact %     │   │
│  └─────────────────────────────────┘   │
└─────────────────────────────────────────┘
```

### Right Column (40% width)

#### Section 1.4: Devices Requiring Attention (Top - 400px height)
```
┌─────────────────────────────────────────┐
│  DEVICES REQUIRING ATTENTION            │
│  Showing: 5 most critical items         │
│  ┌─────────────────────────────────┐   │
│  │ 1. pump-001                     │   │
│  │    [CRITICAL] ✗                 │   │
│  │    Issue: Bearing failure       │   │
│  │    Confidence: 92% ███████░░    │   │
│  │    Timeline: 48 hours           │   │
│  │    [View] [Create WO]           │   │
│  │                                 │   │
│  │ 2. motor-023                    │   │
│  │    [WARNING] ⚠                  │   │
│  │    Issue: Vibration elevated    │   │
│  │    Confidence: 78% ██████░░░    │   │
│  │    Timeline: 1 week             │   │
│  │    [View] [Create WO]           │   │
│  │                                 │   │
│  │ 3. compressor-015               │   │
│  │    [WARNING] ⚠                  │   │
│  │    Issue: Temperature drift     │   │
│  │    Confidence: 85% ███████░░    │   │
│  │    Timeline: 2 weeks            │   │
│  │    [View]                       │   │
│  │                                 │   │
│  │    [View All Issues →]          │   │
│  └─────────────────────────────────┘   │
│  Card Design:                           │
│  - White background with left border    │
│  - Border color matches status          │
│  - Icons for quick identification       │
│  - Hover effect: slight shadow increase │
└─────────────────────────────────────────┘
```

#### Section 1.5: Upcoming Maintenance (Bottom - 250px height)
```
┌─────────────────────────────────────────┐
│    UPCOMING MAINTENANCE (Next 7 Days)   │
│  ┌─────────────────────────────────┐   │
│  │ Jun 24: pump-001 (EMERGENCY)    │   │
│  │         [Status: WO Created]    │   │
│  │                                 │   │
│  │ Jun 25: motor-023 (SCHEDULED)   │   │
│  │         [Status: In Progress]   │   │
│  │                                 │   │
│  │ Jun 27: compressor-015 (PLANNED)│   │
│  │         [Status: Pending]       │   │
│  │                                 │   │
│  │ Jun 28: valve-008 (PREVENTIVE)  │   │
│  │         [Status: Pending]       │   │
│  │                                 │   │
│  │ [View Full Schedule →]          │   │
│  └─────────────────────────────────┘   │
│  Timeline: Mini timeline or list view   │
│  Color coding by priority/type          │
└─────────────────────────────────────────┘
```

---

## 5. TAB 2: DEVICES (Fleet Management)

**Purpose**: Browse, filter, and manage all devices with detailed status

**Layout**: Sidebar filters + responsive grid + expandable side panel

### Left Sidebar (25% width) - Filter Panel
```
┌────────────────────────┐
│ FILTERS                │
├────────────────────────┤
│ 🔍 Search:             │
│ [___________________]  │
│                        │
│ Equipment Type:        │
│ [▼ All] (Dropdown)     │
│  ☐ Pump   (67)         │
│  ☐ Motor  (35)         │
│  ☐ Compressor (12)     │
│  ☐ Valve  (4)          │
│                        │
│ Health Status:         │
│ [▼ All] (Dropdown)     │
│  ☑ Healthy  (175)      │
│  ☑ Warning  (12)       │
│  ☑ Critical (3)        │
│  ☑ Pending  (11)       │
│                        │
│ Health Score:          │
│ [────●─────────] 50%   │
│ Min: 0%  Max: 100%     │
│                        │
│ Last Analyzed:         │
│ [▼ Anytime]            │
│  Last 1 hour           │
│  Last 24 hours         │
│  Last 7 days           │
│  Last 30 days          │
│  Anytime               │
│                        │
│ [Clear All] [Reset]    │
└────────────────────────┘
```

### Main Content (75% width) - Device Grid
```
┌──────────────────────────────────────────────────────────────┐
│ Device Grid View (3-column responsive)                       │
│                                                              │
│ ┌──────────────┬──────────────┬──────────────┐              │
│ │              │              │              │              │
│ │  pump-001    │  motor-023   │  comp-015    │              │
│ │  [CRITICAL]  │  [WARNING]   │  [HEALTHY]   │              │
│ │              │              │              │              │
│ │ ████░░░░░░░  │ ███░░░░░░░░  │ ██████████  │              │
│ │ 45% Health   │ 68% Health   │ 96% Health  │              │
│ │              │              │              │              │
│ │ 5 Anomalies  │ 2 Anomalies  │ 0 Anomalies │              │
│ │ Type: Pump   │ Type: Motor  │ Type: Comp. │              │
│ │ Last: 2h ago │ Last: 45m ago│ Last: 5m ago│              │
│ │              │              │              │              │
│ │ [Details]    │ [Details]    │ [Details]   │              │
│ └──────────────┴──────────────┴──────────────┘              │
│                                                              │
│ [Load More...] [Show All (117)]                            │
└──────────────────────────────────────────────────────────────┘
```

### Side Panel - Device Details (Click device card to open)
```
SIDE PANEL (Slide-in from right):
┌────────────────────────────────────┐
│ ✕ pump-001                         │
├────────────────────────────────────┤
│                                    │
│ STATUS: CRITICAL ✗                │
│ Type: Pump                         │
│ Location: Building A, Floor 2      │
│ Last Service: 45 days ago          │
│                                    │
│ HEALTH METRICS:                    │
│ ├─ Overall Health: 45% ████░░░░   │
│ ├─ Degradation Score: 0.65        │
│ └─ Anomalies Count: 5             │
│                                    │
│ CURRENT READINGS:                  │
│ ├─ Temperature: 78°C (High)       │
│ ├─ Vibration: 12.5mm/s (High)     │
│ ├─ Pressure: 8.2 bar (Normal)     │
│ └─ Flow Rate: 45 L/min (Normal)   │
│                                    │
│ DETECTED ANOMALIES:                │
│ • Temperature spike                │
│ • Vibration increase               │
│ • Bearing noise detected           │
│ • Pressure fluctuation             │
│ • Degradation trending up          │
│                                    │
│ RECOMMENDATION:                    │
│ ACTION: URGENT REPAIR              │
│ Confidence: 92% (High) ████████░░ │
│                                    │
│ REASONING:                         │
│ "Multiple simultaneous anomalies   │
│  indicate bearing failure. Histor- │
│  ical data shows this pattern      │
│  precedes mechanical failure by    │
│  2-5 days."                        │
│                                    │
│ TIMELINE: 48 hours                 │
│ ESTIMATED COST: ~$3,200 repair    │
│                                    │
│ HISTORICAL SPARKLINE (30d):        │
│ 100%╱────╲                         │
│  80%╱      ╲                       │
│  60%╱        ╲                     │
│  40%          ╲                    │
│  20%           ╲                   │
│   0%            ╲────             │
│                                    │
│ IMMEDIATE ACTIONS:                 │
│ ☐ Create Work Order (EMERGENCY)   │
│ ☐ Order spare bearing              │
│ ☐ Schedule technician              │
│ ☐ Notify facility manager          │
│                                    │
│ [Approve & Create WO]              │
│ [Schedule Maintenance]             │
│ [Download Report]                  │
│                                    │
└────────────────────────────────────┘
```

---

## 6. TAB 3: MAINTENANCE (Operations Hub)

**Purpose**: Manage work orders, maintenance schedules, and spare parts

**Layout**: 4 KPI cards + 2-column sections + full-width table

### Top Row - KPI Cards (Full Width)
```
┌────────────────┬────────────────┬────────────────┬────────────────┐
│ WORK ORDERS    │ MAINTENANCE    │ SPARE PARTS    │ WORKLOAD       │
│ (This Month)   │ (Next 7 Days)  │ STATUS         │ FORECAST       │
├────────────────┼────────────────┼────────────────┼────────────────┤
│                │                │                │                │
│      45        │       12       │  In Stock: 156 │ High Load      │
│   [Big #]      │    [Big #]     │ Available: 89% │ Week 1: 23 tasks
│                │                │                │ Week 2: 15 tasks
│ ↑ 12% vs       │ ↓ 8% vs        │ ↑ 3% vs        │ Week 3: 8 tasks
│ last month     │ last month     │ last month     │                │
│                │                │                │                │
└────────────────┴────────────────┴────────────────┴────────────────┘
```

### Middle Section - 2 Columns

#### Left: Urgent Work Orders
```
┌─────────────────────────────────────┐
│ URGENT WORK ORDERS (Next 48h)       │
│                                     │
│ WO-2026-06-23-001 [EMERGENCY]      │
│ pump-001                            │
│ Issue: Bearing failure imminent     │
│ Created: Today 2:15 PM              │
│ Status: ⏳ Awaiting technician     │
│ Priority: ████████░░ 9/10          │
│ [View] [Edit] [Close]              │
│                                     │
│ WO-2026-06-22-045 [HIGH]            │
│ motor-023                           │
│ Issue: Vibration elevated           │
│ Created: Yesterday 10:30 AM         │
│ Status: ⏳ In Progress              │
│ Priority: ████░░░░░░ 6/10          │
│ [View] [Edit] [Close]              │
│                                     │
│ WO-2026-06-21-089 [MEDIUM]          │
│ compressor-015                      │
│ Issue: Preventive maintenance       │
│ Created: 2 days ago                 │
│ Status: ✓ Completed                 │
│ Priority: ███░░░░░░░ 4/10          │
│ [View] [Reopen]                    │
│                                     │
│ [View All (45)] [Create New]       │
└─────────────────────────────────────┘
```

#### Right: Maintenance Calendar
```
┌─────────────────────────────────────┐
│ MAINTENANCE CALENDAR                │
│                                     │
│   June 2026                         │
│ Su Mo Tu We Th Fr Sa                │
│              1  2  3  4             │
│  5  6  7  8  9 10 11                │
│ 12 13 14 15 16 17 18                │
│ 19 20 21 22 23 24 25 ← Today        │
│ 26 27 28 29 30                      │
│                                     │
│ 24 Jun: 3 tasks ●●●                 │
│ 25 Jun: 2 tasks ●●                  │
│ 27 Jun: 1 task ●                    │
│ 28 Jun: 4 tasks ●●●●                │
│                                     │
│ ● = Emergency/Urgent                │
│ ○ = Regular/Planned                 │
│                                     │
│ [Select Date for Details]          │
└─────────────────────────────────────┘
```

### Bottom Section - Spare Parts Inventory Table
```
┌──────────────────────────────────────────────────────────────────┐
│ SPARE PARTS INVENTORY                                            │
├────────────┬─────────────┬──────────┬──────────┬────────┬────────┤
│ Part       │ Type        │ Stock    │ Critical │ Status │ Action │
├────────────┼─────────────┼──────────┼──────────┼────────┼────────┤
│ Bearing    │ Pump        │ 12/15    │ 5        │ ✓ OK   │ Order  │
│ Seal       │ Pump        │ 8/20     │ 3        │ ⚠ Low  │ Order  │
│ Motor      │ Motor       │ 2/5      │ 2        │ ⚠ Low  │ Order  │
│ Impeller   │ Pump        │ 0/10     │ 3        │ ✗ Out  │ Urgent │
│ Belt       │ Motor       │ 25/30    │ 5        │ ✓ OK   │ Monitor│
│ Gasket     │ Compressor  │ 45/50    │ 10       │ ✓ OK   │ Monitor│
├────────────┴─────────────┴──────────┴──────────┴────────┴────────┤
│ [View All] [Reorder] [Supplier Contact]                        │
└──────────────────────────────────────────────────────────────────┘
```

---

## 7. TAB 4: ANALYTICS (Performance & Insights)

**Purpose**: Analyze trends, patterns, and business impact

**Layout**: 3 rows with mixed visualizations

### Row 1: Degradation Trends & Equipment Analysis (2-Column)

#### Left: Top 5 Devices Degradation Trend
```
┌─────────────────────────────────────┐
│ DEGRADATION TRENDS (Last 30 Days)   │
│ Top 5 Declining Devices             │
│                                     │
│ 100%│        ╱╲ ← pump-001 (45%)   │
│  80%│ ╱╲ ╱╲ ╱  ╲ ← motor-023 (68%) │
│  60%│╱  ╲╱  ╲╱ ╲ ← comp-015 (72%) │
│  40%│        ╲  ╲ ← valve-008 (82%)
│  20%│         ╲  ← bear-002 (88%) │
│   0%└──────────╲────────────────  │
│   1d  5d 10d 15d 20d 25d 30d      │
│                                     │
│ Chart Type: Multi-line chart       │
│ Colors: Different for each device   │
│ Legend: Color-coded device names    │
│ Hover: Exact value tooltip          │
└─────────────────────────────────────┘
```

#### Right: Equipment Type Analysis
```
┌─────────────────────────────────────┐
│ EQUIPMENT HEALTH BY TYPE            │
│                                     │
│ Pump                                │
│ ████████░░░░░░░░░░░ 67 devices (57%)
│ Avg Health: 76% ███████░░░          │
│                                     │
│ Motor                               │
│ ██████░░░░░░░░░░░░░ 35 devices (30%)
│ Avg Health: 82% ████████░░          │
│                                     │
│ Compressor                          │
│ ████░░░░░░░░░░░░░░░ 12 devices (10%)
│ Avg Health: 71% ███████░░░          │
│                                     │
│ Valve                               │
│ ██░░░░░░░░░░░░░░░░░  4 devices (3%) │
│ Avg Health: 89% ████████░░          │
│                                     │
│ Chart Type: Horizontal stacked bar  │
│ Colors: By equipment type           │
└─────────────────────────────────────┘
```

### Row 2: Anomaly Patterns & ROI Metrics (2-Column)

#### Left: Anomaly Frequency
```
┌─────────────────────────────────────┐
│ ANOMALY PATTERNS (Last 30 Days)     │
│                                     │
│ Temperature_high:                   │
│ ██████████░░░░░░░░░░░░░░░░░░░░░░░░ 42
│                                     │
│ Vibration_high:                     │
│ ████████░░░░░░░░░░░░░░░░░░░░░░░░░░ 28
│                                     │
│ Pressure_low:                       │
│ ████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 15
│                                     │
│ Noise_unusual:                      │
│ ███░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  8
│                                     │
│ Leakage:                            │
│ ██░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  5
│                                     │
│ Other:                              │
│ █░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  2
│                                     │
│ Chart Type: Horizontal bar          │
│ Most common: Temperature_high       │
│ (42 instances across 23 devices)   │
└─────────────────────────────────────┘
```

#### Right: Maintenance ROI
```
┌─────────────────────────────────────┐
│ MAINTENANCE ROI (Current Month)     │
│                                     │
│ Maintenance Cost:                   │
│ $18,500                             │
│                                     │
│ Downtime Prevented:                 │
│ $156,000                            │
│                                     │
│ Equipment Replacement Prevented:    │
│ $87,200 (avg)                       │
│                                     │
│ ─────────────────────────────────   │
│ NET SAVINGS:                        │
│ $224,700 ↑↑↑                        │
│                                     │
│ ROI: 1,215% 📈                      │
│                                     │
│ Devices Saved from Critical Failure:
│ 23 devices                          │
│                                     │
│ Avg Resolution Time: 2.3 days       │
│                                     │
│ Display: Large dashboard metrics    │
│ Colors: Green for positive values   │
└─────────────────────────────────────┘
```

### Row 3: Failure Prediction Timeline (Full Width)
```
┌──────────────────────────────────────────────────────────────────┐
│ FAILURE PREDICTION TIMELINE (Next 90 Days)                       │
│                                                                  │
│  Days to Failure:  0-7d      7-14d     14-30d    30-90d        │
│                   URGENT     HIGH      MEDIUM    LOW            │
│                                                                  │
│                  ●          ●●●        ●●●●●   ●●●●●●●        │
│                 [1]        [5]        [12]     [28]            │
│                                                                  │
│ Timeline Visualization:                                         │
│                                                                  │
│ pump-001 ────────● (2d)   CRITICAL - Action required           │
│ motor-023 ────────────● (5d)   HIGH - Monitor closely          │
│ bearing-002 ────────────────────● (12d)   MEDIUM - Schedule    │
│ valve-008 ──────────────────────────────────────● (45d)        │
│ compressor-015 ──────────────────────────────────────● (67d)   │
│ pump-045 ────────────────────────────────────────────● (78d)   │
│                                                                  │
│ Chart Type: Scatter timeline visualization                      │
│ X-axis: Days to failure (0-90)                                  │
│ Y-axis: Device names (sorted by urgency)                        │
│ Colors: Red (critical), Orange (high), Yellow (medium), Green   │
└──────────────────────────────────────────────────────────────────┘
```

---

## 8. TAB 5: ALERTS (Critical Issues Management)

**Purpose**: Centralized issue tracking and priority management

**Layout**: Sidebar filters + priority-based list

### Left Sidebar (25% width) - Alert Filters
```
┌────────────────────────┐
│ ALERT FILTERS          │
├────────────────────────┤
│ Severity:              │
│ ☑ Critical (3)         │
│ ☑ High (8)             │
│ ☐ Medium (12)          │
│ ☐ Low (34)             │
│                        │
│ Alert Type:            │
│ ☑ Health Alert         │
│ ☑ Anomaly              │
│ ☑ Maintenance          │
│ ☐ System               │
│                        │
│ Device Type:           │
│ ☑ Pump                 │
│ ☑ Motor                │
│ ☐ Compressor           │
│ ☐ Valve                │
│                        │
│ Time Range:            │
│ ⊙ Last 24h (selected)  │
│ ○ Last 7d              │
│ ○ Last 30d             │
│ ○ All time             │
│                        │
│ [Clear] [Reset]        │
└────────────────────────┘
```

### Main Content (75% width) - Alert List
```
┌──────────────────────────────────────────────────────────────┐
│ ACTIVE ALERTS (11 Critical/High Alerts)                      │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│ CRITICAL (3)                                                │
│ ─────────────────────────────────────────────────────────   │
│                                                              │
│ ✗ pump-001 - Bearing Failure                                │
│   ┌──────────────────────────────────────────────────────┐ │
│   │ Detected: 2h ago                                     │ │
│   │ Device: pump-001 (Pump)                              │ │
│   │ Issue: Multiple bearing anomalies detected           │ │
│   │ Confidence: 92% ████████░░                          │ │
│   │ Timeline: 48 hours to failure                        │ │
│   │ Recommended Action: URGENT REPAIR                   │ │
│   │ Status: ⚠ Work Order Created (WO-2026-06-23-001)   │ │
│   │ [Dismiss] [View Details] [Create WO] [Escalate]    │ │
│   └──────────────────────────────────────────────────────┘ │
│                                                              │
│ ✗ bearing-045 - Critical Vibration                           │
│   ┌──────────────────────────────────────────────────────┐ │
│   │ Detected: 5h ago                                     │ │
│   │ Device: bearing-045 (Motor-attached)                 │ │
│   │ Issue: Vibration exceeds safe threshold              │ │
│   │ Confidence: 88% ███████░░░                          │ │
│   │ Timeline: 72 hours to failure                        │ │
│   │ Recommended Action: INSPECT & REPAIR                │ │
│   │ Status: ⏳ Awaiting Technician                       │ │
│   │ [Dismiss] [View Details] [Escalate]                 │ │
│   └──────────────────────────────────────────────────────┘ │
│                                                              │
│ ✗ compressor-015 - Efficiency Drop                           │
│   ┌──────────────────────────────────────────────────────┐ │
│   │ Detected: 12h ago                                    │ │
│   │ Device: compressor-015 (Compressor)                  │ │
│   │ Issue: Output efficiency dropped 45%                 │ │
│   │ Confidence: 95% █████████░                          │ │
│   │ Timeline: 2-3 days to critical state                │ │
│   │ Recommended Action: SCHEDULE SERVICE                │ │
│   │ Status: ⏳ In Progress                               │ │
│   │ [Dismiss] [View Details] [Expedite]                │ │
│   └──────────────────────────────────────────────────────┘ │
│                                                              │
│ HIGH (8)                                                    │
│ ─────────────────────────────────────────────────────────   │
│                                                              │
│ ⚠ motor-023 - Elevated Vibration                             │
│   ┌──────────────────────────────────────────────────────┐ │
│   │ Detected: 3h ago                                     │ │
│   │ Device: motor-023 (Motor)                            │ │
│   │ Issue: Vibration trending upward                     │ │
│   │ Confidence: 78% ██████░░░░                          │ │
│   │ Timeline: 1-2 weeks to critical state               │ │
│   │ Recommended Action: MONITOR CLOSELY                 │ │
│   │ Status: ✓ Monitoring Active                         │ │
│   │ [Dismiss] [View Details] [Schedule Maint.]          │ │
│   └──────────────────────────────────────────────────────┘ │
│                                                              │
│ [Load More...] [Show All (11)]                             │
└──────────────────────────────────────────────────────────────┘
```

---

## 9. UI Component Specifications

### Health Bars
```
Style: Gradient fill with percentage indicator
Colors based on health percentage:
  - 0-25%:   Crimson Red (#dc2626)
  - 26-50%:  Amber/Gold (#f59e0b)
  - 51-75%:  Teal/Cyan (#0d9488)
  - 76-100%: Emerald Green (#10b981)

Height: 8-12px
Border-radius: 4px
Animation: Smooth width transition (0.3s cubic-bezier)
Hover: Tooltip showing exact percentage, last update time
```

### Status Badges
```
Styles:
  ✓ Healthy: Green badge (#10b981) with checkmark icon
  ⚠ Warning: Amber badge (#f59e0b) with warning triangle
  ✗ Critical: Red badge (#dc2626) with X icon
  ⏳ Pending: Gray badge (#9ca3af) with hourglass icon

Size: Small (badge style)
Font-size: 12px, semibold
Padding: 4-6px 8-12px
Border-radius: 16px (pill-shaped)

Animation: Subtle pulse (1s cycle) for critical items
```

### Confidence Indicators
```
Display: Circular progress bar + percentage text
Format: "92% [Confidence Level]"
Size: 60px diameter (can vary)

Color zones:
  - 0-60%:    Orange (#f59e0b) - Low confidence
  - 61-85%:   Yellow (#eab308) - Medium confidence
  - 86-100%:  Green (#10b981) - High confidence

Animation: None (static metric)
Hover: Show confidence source (rule-based or LLM-enhanced)
```

### Buttons & Call-to-Action
```
Primary CTA (Main action):
  Background: Teal (#0d9488)
  Text: White
  Hover: Darker teal (#0f766e)
  Active: Even darker (#065f46)
  Padding: 8-12px 16-20px
  Border-radius: 6px
  Font-weight: 600

Secondary CTA (Less important):
  Background: Light gray (#e2e8f0)
  Text: Navy (#1a2d4d)
  Hover: Medium gray (#cbd5e1)
  Padding: 8-12px 16-20px
  Border-radius: 6px
  Font-weight: 600

Danger CTA (Delete/Critical):
  Background: Red (#dc2626)
  Text: White
  Hover: Darker red (#b91c1c)
  Padding: 8-12px 16-20px
  Border-radius: 6px
  Font-weight: 600

All buttons:
  Cursor: pointer
  Transition: All 0.2s ease
  Active state: Slight scale down (0.98)
  Disabled state: Opacity 0.5, cursor not-allowed
```

### Cards
```
Background: White (#ffffff)
Border: 1px solid #e2e8f0 (light gray)
Padding: 16px
Border-radius: 8px
Box-shadow: 0 1px 3px rgba(0,0,0,0.1)

Hover:
  Box-shadow: 0 4px 12px rgba(0,0,0,0.15)
  Transform: translateY(-2px)
  Transition: All 0.2s ease

Color-coded left border (4px):
  - Healthy: Green #10b981
  - Warning: Amber #f59e0b
  - Critical: Red #dc2626
  - Info: Blue #0ea5e9
  - Default: Gray #e2e8f0
```

---

## 10. Typography & Spacing

### Font Stack
```
Primary: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif
Fallback: sans-serif
Monospace (codes): "Monaco", "Courier New", monospace
```

### Font Sizes
```
Page Title (h1): 32px, Bold/700, Color: #1a2d4d
Section Header (h2): 20px, SemiBold/600, Color: #1a2d4d
Card Title (h3): 16px, SemiBold/600, Color: #1a2d4d
Body Text: 14px, Regular/400, Color: #475569
Small Text: 12px, Regular/400, Color: #64748b
Label Text: 12px, SemiBold/600, Color: #64748b
Mini Text: 11px, Regular/400, Color: #cbd5e1
```

### Line Heights
```
Headings: 1.2
Body text: 1.6
Compact text: 1.4
List items: 1.8
```

### Spacing Scale (8px base unit)
```
xs:  4px
sm:  8px
md:  16px
lg:  24px
xl:  32px
2xl: 48px
```

### Common Spacings
```
Header height: 70px
Sticky KPI row: 16px padding vertical, 20px horizontal
Section padding: 24px
Card padding: 16px
Gap between grid items: 16px
Margin between sections: 24-32px
```

---

## 11. Responsive Design Breakpoints

### Desktop (1920px and above)
```
Overview:    2-column layout (60/40)
Devices:     Sidebar (25%) + 3-column grid (75%)
Maintenance: 4 cards + 2 columns + full table
Analytics:   2 columns + 2 columns + full width
Alerts:      Sidebar (25%) + Detailed list (75%)
```

### Tablet (768px - 1919px)
```
Overview:    1-column stacked
Devices:     Sidebar (30%) + 2-column grid (70%)
Maintenance: 2 cards per row + 2 sections
Analytics:   1-column stacked
Alerts:      Simplified with expand/collapse
```

### Mobile (< 768px)
```
Sidebar filters: Drawer/modal with hamburger menu
Grid items: 1-column full width
Chart height: Reduced (max 250px)
Font sizes: Reduced by 10-15%
Padding/margins: Reduced by 25-50%
Side panels: Full-screen modals
Tables: Horizontal scroll or card layout
Buttons: Larger touch targets (48px min)
```

---

## 12. Interactive Features & Animations

### Tab Switching
```
Animation: Fade + slide (0.3s cubic-bezier)
Effect: Smooth content transition, underline animation
```

### Expand/Collapse
```
Animation: Smooth height transition (0.25s ease)
Effect: Chevron icon rotation
```

### Chart Interactions
```
Hover: Show tooltip with exact values
Click: Drill-down or filter related data
Animation: Smooth appearance (0.2s)
```

### Card Click
```
Action: Slide-in side panel from right
Animation: 0.3s cubic-bezier ease
Background: Slight overlay dimming
Close: Click X or outside panel
```

### Filter Changes
```
Animation: Loading spinner during data refetch
Duration: Show spinner for minimum 200ms (even if fast)
Effect: Fade in new results
```

### Mobile Menu
```
Animation: Slide-in from left (0.3s)
Background: Semi-transparent overlay
Close: Click overlay or X button
```

### Real-time Updates
```
Animation: Gentle pulse on changed values
Duration: 0.5s ease-in-out
Effect: Draws attention to updates
```

---

## 13. Data Refresh Strategy

### Automatic Refresh
```
KPI Cards (Top):      Every 30 seconds
Device Grid:          Every 1 minute
Alert List:           Every 20 seconds
Analytics Charts:     Every 5 minutes
Maintenance Calendar: Every 10 minutes
Overall health:       Every 45 seconds
```

### Manual Refresh
```
Global refresh button: Top right corner
Per-section refresh: Individual section refresh icons
Last updated timestamp: Shown in footer
```

### Auto-pause
```
Pause updates when:
  - Tab is not visible (browser tab in background)
  - Mobile browser in background
  - User idle for 5 minutes (show notification)
  - User actively interacting (pause for 30 seconds)
```

---

## 14. Accessibility Features

```
ARIA Labels: All interactive elements
Keyboard Navigation: Tab, Enter, Escape support
Focus Indicators: Visible outline for keyboard users
Color Contrast: All text ≥ 4.5:1 WCAG AA
Screen Reader: Semantic HTML + ARIA descriptions
Alt Text: Charts have data download option
Font Size: Scalable, minimum 12px
Zoom: Support up to 200% zoom
```

---

## 15. Chart Libraries & Implementation

### Chart.js Integration
```
Charts to implement:
  ✓ Radial/Gauge Chart (Overview - Fleet Health)
  ✓ Doughnut/Pie Chart (Overview - Status Distribution)
  ✓ Line Chart (Overview - 7-day trend)
  ✓ Multi-line Chart (Analytics - Degradation trends)
  ✓ Horizontal Bar Chart (Analytics - Equipment type)
  ✓ Horizontal Bar Chart (Analytics - Anomaly patterns)
  ✓ Scatter Timeline (Analytics - Failure prediction)

Libraries:
  - Chart.js v3.9.1+ (via CDN)
  - Optional: D3.js for complex visualizations (future)
  - Optional: Plotly for interactive scientific charts
```

---

## 16. Performance Optimizations

```
Frontend:
  - Lazy load charts (only when scrolled into view)
  - Debounce filter changes (300ms)
  - Cache chart instances
  - Minimize re-renders

Backend:
  - Pagination for device lists (limit 50 per page)
  - Cache aggregated metrics (5-min TTL)
  - Use indexes for filtering queries
  - Compression for API responses (gzip)

Network:
  - Optimize API payload size
  - Use WebSocket for real-time updates (future)
  - Implement request cancellation (abort)
```

---

## 17. Implementation Notes

### Technology Stack
```
Frontend: Vanilla HTML/CSS/JavaScript (no framework needed yet)
Charts: Chart.js 3.9.1 (CDN)
Backend: FastAPI (orchestrator service)
Database: DynamoDB (device data)
Real-time: WebSocket (optional for Phase 2)
Styling: Inline CSS (single file approach like phase2_8)
```

### File Structure
```
src/dashboard/
├── templates/
│   └── index.html (Main dashboard file - all HTML/CSS/JS)
├── static/
│   ├── css/
│   │   └── dashboard.css (if separated)
│   └── js/
│       └── dashboard.js (if separated)
├── app.py (Flask/FastAPI route)
└── requirements.txt
```

### Key Endpoints Needed
```
GET  /api/devices - List all devices
GET  /api/devices/{id} - Device details
GET  /api/fleet-summary - KPI metrics
GET  /api/alerts - Active alerts
GET  /api/work-orders - Work order list
GET  /api/maintenance-schedule - Upcoming maintenance
GET  /api/analytics - Trend data
GET  /api/health - System health check
```

---

## 18. Next Steps (Implementation Phases)

### Phase 1: Basic Structure
1. Create main HTML file with header, KPIs, tabs
2. Implement Overview tab with basic charts
3. Create responsive grid layout
4. Add Tab 1: Overview complete

### Phase 2: Device Management
5. Implement Devices tab with grid view
6. Add side panel for device details
7. Add filter sidebar
8. Implement responsive design

### Phase 3: Operations
9. Implement Maintenance tab
10. Add work order management
11. Add spare parts inventory

### Phase 4: Analytics & Alerts
12. Implement Analytics tab with all visualizations
13. Implement Alerts tab with priority sorting
14. Add advanced filtering

### Phase 5: Polish & Optimization
15. Add animations and transitions
16. Implement real-time updates
17. Add dark mode (optional)
18. Performance optimization

---

## 19. Design Reference

**Base Reference**: reference/phase2_8/templates/dashboard.html
- Single HTML file approach (inline CSS)
- Chart.js for visualizations
- Responsive grid layout
- Purple gradient theme (to be updated to professional navy/teal)

**Improvements in Phase 3.1**:
- Professional color scheme (navy/teal instead of purple)
- Hierarchical layout (not flat)
- 5 tabs instead of 4
- Rich visualizations and graphs
- Client-centric (no agent/MCP details)
- Better organization and information hierarchy
- Side panel for device details
- Advanced filtering and sorting

---

## 20. Questions & Confirmations Needed

1. **Dashboard Page Name**: ✅ **CONFIRMED** - "Agentic-Eco-Sentinel Dashboard"
2. **Flask vs FastAPI**: Use Flask like phase2_8, or FastAPI like the orchestrator?
3. **Single File vs Separated**: Keep as single HTML file, or split CSS/JS?
4. **Dark Mode**: Include dark mode toggle?
5. **Real-time WebSocket**: Include WebSocket for live updates?
6. **API Endpoints**: Should we create these in the orchestrator service?
7. **Sample Data**: Use mock data or integrate with live API?
8. **Deployment**: Docker container for dashboard service?

---

**Document Version**: 1.0  
**Last Updated**: June 23, 2026  
**Dashboard Name**: Agentic-Eco-Sentinel Dashboard ✅ CONFIRMED  
**Status**: Design specification ready for implementation
