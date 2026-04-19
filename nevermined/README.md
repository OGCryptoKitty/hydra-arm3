# HYDRA — Nevermined Agent Registration

Configuration for registering HYDRA on the [Nevermined](https://nevermined.io/) agent marketplace.

## Registration

Using the Nevermined TypeScript SDK:

```typescript
import { Payments } from '@nevermined-io/payments'

const payments = new Payments({ environment: 'arbitrum' })

const agentDID = await payments.agents.registerAgentAndPlan({
  name: 'HYDRA Regulatory Intelligence',
  description: 'Real-time regulatory intelligence for prediction markets. 22 paid endpoints via x402.',
  serviceEndpoint: 'https://hydra-api-nlnj.onrender.com',
  openApiUrl: 'https://hydra-api-nlnj.onrender.com/openapi.json',
  pricingToken: '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913', // USDC
  amountOfCredits: 100,
  tags: ['regulatory', 'prediction-markets', 'x402', 'oracle', 'defi']
})
```

## Config

See `hydra_agent_config.json` for the full agent metadata used during registration.
