# Agent Trust Network - Web UI

Interactive visualization of multi-agent trust networks with PageRank-based trust scoring.

## Features

- **Network Visualization**: Interactive force-directed graph using D3.js
- **Real-time Simulation**: Step-by-step or batch simulation of agent interactions
- **Trust Propagation**: PageRank-based trust score calculation
- **Agent Management**: Add, view, and delete agents with different behaviors
- **Detailed Metrics**: Network health, trust distribution, and individual agent metrics
- **Import/Export**: Save and load network configurations as JSON
- **Responsive Design**: Clean, dark-themed UI with Tailwind CSS

## Technology Stack

- **Frontend**: React 18 + TypeScript + Vite
- **Visualization**: D3.js (Force-directed graph)
- **Styling**: Tailwind CSS
- **Build Tool**: Vite

## Getting Started

### Prerequisites

- Node.js 18+ and npm/yarn/pnpm

### Installation

```bash
# Install dependencies
npm install
```

### Development

```bash
# Start development server
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) in your browser.

### Build for Production

```bash
# Build the project
npm run build

# Preview production build
npm run preview
```

## Usage

### Adding Agents

1. Enter a name in the "Add Agent" section
2. Select a behavior type:
   - 🟢 **Cooperative**: Always tries to help (90% success rate)
   - 🟡 **Neutral**: Helps based on trust level
   - 🔴 **Malicious**: Rarely cooperates (20% success rate)
   - ⚫ **Adversarial**: Actively harms others (10% success rate)
3. Click "Add Agent"

### Running Simulations

- **Step ▶**: Run one simulation step
- **×10 ⏩**: Run 10 steps
- **×50**: Run 50 steps
- **Reset**: Reset network to initial state

Each step simulates random interactions between agents, updating trust scores based on success/failure.

### Exploring the Network

- **Click** on a node to view detailed agent information
- **Hover** over nodes to see quick stats
- **Drag** nodes to rearrange the graph
- **Scroll/Zoom** to navigate the network

### Understanding Metrics

- **Trust Score**: Computed using PageRank algorithm (0-100%)
- **Network Health**: Overall network quality (trust distribution + confidence)
- **Volatility Index**: How much trust scores are changing
- **Confidence Index**: How reliable the trust scores are
- **Agent Trends**: Rising, falling, or stable trust

### Import/Export

- **Export**: Download current network configuration as JSON
- **Import**: Load a previously saved network configuration

## Project Structure

```
agent-trust-web/
├── src/
│   ├── components/       # React components
│   │   ├── NetworkGraph.tsx       # D3.js graph visualization
│   │   ├── ControlPanel.tsx       # Simulation controls
│   │   ├── StatsPanel.tsx         # Network statistics
│   │   ├── AgentDetailsPanel.tsx  # Agent details and list
│   │   ├── Header.tsx             # Top header with export/import
│   │   └── Tooltip.tsx            # Hover tooltip
│   ├── types.ts          # TypeScript type definitions
│   ├── trustNetwork.ts   # Core simulation logic (browser-based)
│   ├── App.tsx           # Main application component
│   ├── main.tsx          # Application entry point
│   └── index.css         # Global styles + Tailwind
├── public/               # Static assets
├── index.html            # HTML template
├── tailwind.config.js    # Tailwind CSS configuration
├── tsconfig.json         # TypeScript configuration
├── vite.config.ts        # Vite configuration
└── package.json          # Dependencies
```

## Deployment

### Vercel

```bash
# Install Vercel CLI
npm i -g vercel

# Deploy
vercel
```

Or connect your GitHub repository to Vercel for automatic deployments.

### Netlify

```bash
# Install Netlify CLI
npm i -g netlify-cli

# Build and deploy
npm run build
netlify deploy --prod --dir=dist
```

### Static Hosting

For any static hosting service (GitHub Pages, Cloudflare Pages, etc.):

1. Build the project: `npm run build`
2. Upload the contents of the `dist/` directory
3. Ensure the server supports single-page application routing (redirect all routes to `index.html`)

### Docker

```dockerfile
FROM node:18-alpine as builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

Build and run:

```bash
docker build -t agent-trust-web .
docker run -p 8080:80 agent-trust-web
```

## Testing

The project uses [Vitest](https://vitest.dev/) for unit testing.

```bash
# Run tests
npm test

# Run tests in watch mode
npm run test:watch

# Run tests with coverage
npm run test:coverage
```

### Test Structure

Tests are located in `tests/` and mirror the `src/` structure:

```
tests/
├── trustNetwork.test.ts         # Core simulation logic (30+ cases)
└── trustNetworkExtended.test.ts # Extended edge cases & metrics (20+ cases)
```

**Total: 51 tests** across 2 test files.

### What's Tested

| Area | Coverage |
|------|----------|
| Initialization | Default agents, relations, behavior distribution |
| Agent CRUD | Add/remove agents, relation cleanup |
| Trust Relations | Set/get weights, clamping [0,1], nonexistent agents |
| Trust Calculation | PageRank scores in [0,1], single-agent edge case |
| Simulation | Step counting, batch simulation, 0/1 agent edge cases |
| Metrics | Network health, trust distribution, empty network |
| Agent Metrics | Individual metrics, trends, reliability, velocity |
| Interaction Details | Cooperation refusal, trust weight updates, history capping |
| Import/Export | JSON round-trip, invalid JSON handling |
| Reset | State restoration |

### Writing New Tests

```typescript
import { describe, it, expect, beforeEach } from 'vitest';
import { TrustNetworkSimulation } from '../src/trustNetwork';

describe('MyFeature', () => {
  let sim: TrustNetworkSimulation;
  beforeEach(() => { sim = new TrustNetworkSimulation(); });

  it('should work', () => {
    // test code
  });
});
```

## API Reference

### `TrustNetworkSimulation`

Core simulation engine. All state is maintained in-memory.

#### Constructor

```typescript
new TrustNetworkSimulation()
```

Creates a simulation with 5 default agents: Alice (cooperative), Bob (cooperative), Charlie (neutral), David (neutral), Eve (malicious).

#### Agent Management

| Method | Signature | Description |
|--------|-----------|-------------|
| `addAgent` | `(config: { id, name, behavior, initialTrust?, expertise?, reliability? }) => void` | Add agent to network |
| `removeAgent` | `(id: string) => void` | Remove agent and its relations |

#### Trust Operations

| Method | Signature | Description |
|--------|-----------|-------------|
| `setTrustRelation` | `(from: string, to: string, weight: number) => void` | Set trust weight (clamped to [0,1]) |
| `getTrustWeight` | `(from: string, to: string) => number` | Get trust weight (0 if no relation) |
| `calculateTrustScores` | `() => void` | Run PageRank to update all trust scores |

#### Simulation

| Method | Signature | Description |
|--------|-----------|-------------|
| `simulateStep` | `() => void` | Run one interaction round |
| `simulate` | `(steps: number) => void` | Run N steps |
| `reset` | `() => void` | Reset to default state |

#### Data Access

| Method | Signature | Returns |
|--------|-----------|--------|
| `getStats` | `() => NetworkStats` | Agent count, relation count, avg trust, behavior distribution |
| `getMetrics` | `() => NetworkMetrics` | Network health, volatility, confidence, trust distribution |
| `getAgentMetrics` | `(id: string) => AgentMetrics \| null` | Individual agent trend, reliability, velocity |
| `getNetworkData` | `() => NetworkData` | Full snapshot: agents, relations, stats, metrics, stepCount |

#### Persistence

| Method | Signature | Description |
|--------|-----------|-------------|
| `exportConfig` | `() => string` | Serialize network to JSON |
| `importConfig` | `(json: string) => void` | Restore from JSON (invalid JSON is ignored) |

#### Key Types

```typescript
type AgentBehavior = 'cooperative' | 'neutral' | 'malicious' | 'adversarial';

interface Agent {
  id: string; name: string; behavior: AgentBehavior;
  trustScore: number; interactions: number; successRate: number;
}

interface NetworkMetrics {
  totalAgents: number; averageTrust: number; networkHealth: number;
  trustDistribution: { high: number; medium: number; low: number };
  volatilityIndex: number; confidenceIndex: number;
}
```

Full type definitions: [`src/types.ts`](src/types.ts)

## Development

### Code Style

The project uses ESLint for code linting:

```bash
# Check for issues
npm run lint

# Auto-fix issues
npm run lint:fix
```

### Type Checking

```bash
# Run TypeScript compiler
npm run type-check
```

## Algorithm Details

### Trust Score Calculation

The trust score uses a PageRank-style algorithm:

1. **Initialization**: All agents start with equal trust (1/n)
2. **Iteration**: For each agent, calculate incoming trust from neighbors
3. **Damping**: Apply damping factor (0.85) to prevent "trust sinks"
4. **Normalization**: Scale scores to 0-1 range

Formula:
```
Trust(agent) = (1 - d) / n + d * Σ(Trust(source) * weight / Σ outgoing_weights)
```

Where:
- `d` = damping factor (0.85)
- `n` = total number of agents
- `weight` = trust weight from source to agent

### Simulation Steps

Each simulation step:
1. Records trust snapshots for metrics
2. Simulates random agent interactions
3. Updates trust relations based on success/failure
4. Recalculates trust scores
5. Updates network metrics

## License

MIT

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
