import { useState } from "react";
import NonControllablePage from "./NonControllablePage";
import NcScenarioComparisonPage from "./NcScenarioComparisonPage";
import ControllablePage from "./ControllablePage";
import CtrlScenarioComparisonPage from "./CtrlScenarioComparisonPage";

const TABS = [
  { id: "non-controllable",   label: "Non-Controllable",           desc: "Employee-related costs" },
  { id: "nc-comparison",      label: "NC Scenario Comparison",     desc: "Compare scenarios side by side" },
  { id: "controllable",       label: "Controllable",               desc: "Vendor & contract costs" },
  { id: "ctrl-comparison",    label: "Ctrl Scenario Comparison",   desc: "Compare controllable scenarios" },
];

export default function BudgetPlanningPage() {
  const [activeTab, setActiveTab] = useState("non-controllable");

  return (
    <div className="p-6 max-w-[1400px] mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-gray-900">Budget Planning</h1>
        <p className="text-sm text-gray-500 mt-0.5">
          Plan and model department budgets by fiscal year
        </p>
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 border-b border-gray-200 mb-6">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px ${
              activeTab === tab.id
                ? "border-indigo-600 text-indigo-600"
                : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === "non-controllable" && <NonControllablePage />}
      {activeTab === "nc-comparison"    && <NcScenarioComparisonPage />}
      {activeTab === "controllable"     && <ControllablePage />}
      {activeTab === "ctrl-comparison"  && <CtrlScenarioComparisonPage />}
    </div>
  );
}
