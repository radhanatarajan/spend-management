import { useState } from "react";
import NonControllablePage from "./NonControllablePage";
import NcScenarioComparisonPage from "./NcScenarioComparisonPage";

const TABS = [
  { id: "non-controllable", label: "Non-Controllable", desc: "Employee-related costs" },
  { id: "nc-comparison",    label: "NC Scenario Comparison", desc: "Compare scenarios side by side" },
  { id: "controllable",     label: "Controllable", desc: "Vendor & contract costs", soon: true },
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
            onClick={() => !tab.soon && setActiveTab(tab.id)}
            disabled={tab.soon}
            className={`relative px-4 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px ${
              activeTab === tab.id
                ? "border-indigo-600 text-indigo-600"
                : tab.soon
                ? "border-transparent text-gray-300 cursor-not-allowed"
                : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
            }`}
          >
            {tab.label}
            {tab.soon && (
              <span className="ml-1.5 text-[10px] bg-gray-100 text-gray-400 px-1.5 py-0.5 rounded-full">
                Soon
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === "non-controllable" && <NonControllablePage />}
      {activeTab === "nc-comparison" && <NcScenarioComparisonPage />}
    </div>
  );
}
