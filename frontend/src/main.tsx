import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { PlanProvider } from "./context/PlanContext";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <PlanProvider>
      <App />
    </PlanProvider>
  </React.StrictMode>
);
