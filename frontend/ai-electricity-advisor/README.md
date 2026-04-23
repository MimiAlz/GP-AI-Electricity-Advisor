# Frontend (React + Vite)

This frontend is a React app (Vite template) that connects to the backend for authentication, house management, and electricity bill forecasting.

## Real Data Forecasting Flow

- When a user requests a forecast for a house, the frontend calls the backend endpoint `/users/{national_id}/houses/{house_id}/forecasts`.
- The backend fetches all available smart meter readings for that house, using pagination to bypass the 1000-row Supabase/PostgREST limit.
- The backend preprocesses the readings, runs the forecasting model, and returns the predicted energy usage, estimated bill, and tariff tier.
- The frontend displays these results to the user.

## Development

This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the ESLint configuration

If you are developing a production application, we recommend using TypeScript with type-aware lint rules enabled. Check out the [TS template](https://github.com/vitejs/vite/tree/main/packages/create-vite/template-react-ts) for information on how to integrate TypeScript and [`typescript-eslint`](https://typescript-eslint.io) in your project.
