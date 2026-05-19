import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import Layout from "./components/Layout";
import ProtectedRoute from "./components/ProtectedRoute";
import LoginPage from "./pages/Login/LoginPage";
import HomePage from "./pages/Home/HomePage";
import SpendPage from "./pages/Spend";
import ContractsPage from "./pages/Contracts/ContractsPage";
import BudgetPlanningPage from "./pages/BudgetPlanning/BudgetPlanningPage";
import ForecastingPage from "./pages/Forecasting/ForecastingPage";
import ReportsPage from "./pages/Reports/ReportsPage";

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/*"
            element={
              <ProtectedRoute>
                <Layout>
                  <Routes>
                    <Route path="/"                element={<HomePage />} />
                    <Route path="/spend"           element={<SpendPage />} />
                    <Route path="/contracts"       element={<ContractsPage />} />
                    <Route path="/budget-planning" element={<BudgetPlanningPage />} />
                    <Route path="/forecasting"     element={<ForecastingPage />} />
                    <Route path="/reports"         element={<ReportsPage />} />
                  </Routes>
                </Layout>
              </ProtectedRoute>
            }
          />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
