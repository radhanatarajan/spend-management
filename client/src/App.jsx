import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import SpendPage from "./pages/Spend";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/spend" replace />} />
        <Route path="/spend" element={<SpendPage />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
