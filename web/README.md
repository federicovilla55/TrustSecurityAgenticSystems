Web interface bootstrapped with [next.js](https://nextjs.org/)

## Getting Started

First, to run the developed frontend:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

## Directory structure

The pages boostrap a simple frontend that contains the basic agent functionalities, permitting a user to connect with the FastAPI backend.

### Authentication Page

The _Authentication_ Page, reachable at `/auth`, contains the logic for creating a new user and saving it in the database and to login with previously created credentials.
This page is fundamental for getting JWT token, used for later endpoints interactions with the FastAPI backend.

### Dashboard Page

The _Dashboard_ page shows:
- public information, 
- private information,
- policies,
- connections established by an agent,
- suggested connections,
- sent connection requests.

The two latter two elements buttons to express feedback on such connections (either `Accept` or `Reject`). 
The user can modify the first three elements by clicking on the pencil button.

### Settings Page

The settings page shows: 
- buttons to either `Pause`/`Resume` or `Delete` the personal agent
- buttons to change the models used to evaluate the pairing connections
- Edit box for the agent's public information, private information and policies.