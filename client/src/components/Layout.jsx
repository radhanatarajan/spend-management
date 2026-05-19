import { NavLink, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const NAV_ITEMS = [
  {
    to: "/",
    label: "Home",
    end: true,
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
      </svg>
    ),
  },
  {
    to: "/spend",
    label: "Spend Analytics",
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
      </svg>
    ),
  },
  {
    to: "/contracts",
    label: "Contract Database",
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
    ),
  },
  {
    to: "/budget-planning",
    label: "Budget Planning",
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
      </svg>
    ),
  },
  {
    to: "/forecasting",
    label: "Forecasting",
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
      </svg>
    ),
  },
];

const REPORT_ITEMS = [
  { to: "/reports/spend",      label: "Spend Report" },
  { to: "/reports/contracts",  label: "Contract Report" },
  { to: "/reports/forecast",   label: "Forecast Report", disabled: true },
  { to: "/reports/budget",     label: "Budget Report",   disabled: true },
];

const ROLE_BADGE = {
  ADMIN:         "bg-red-100 text-red-700",
  BIZ_ADMIN:     "bg-orange-100 text-orange-700",
  SERVICE_OWNER: "bg-blue-100 text-blue-700",
  READ_ONLY:     "bg-gray-100 text-gray-600",
};

const ROLE_LABEL = {
  ADMIN:         "Admin",
  BIZ_ADMIN:     "Biz Admin",
  SERVICE_OWNER: "Svc Owner",
  READ_ONLY:     "Read Only",
};

export default function Layout({ children }) {
  const { user, logout } = useAuth();
  const location = useLocation();
  const inReports = location.pathname.startsWith("/reports");

  return (
    <div className="flex h-screen bg-gray-50 overflow-hidden">
      {/* Sidebar */}
      <aside className="flex flex-col w-56 shrink-0 bg-white border-r border-gray-200">
        {/* Brand */}
        <div className="flex items-center gap-2.5 px-5 h-16 border-b border-gray-200">
          <div className="w-7 h-7 rounded-lg bg-indigo-600 flex items-center justify-center shrink-0">
            <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <span className="text-sm font-semibold text-gray-900 leading-tight">Spend<br />Management</span>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-4 overflow-y-auto space-y-0.5">
          {NAV_ITEMS.map(({ to, label, icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-indigo-50 text-indigo-700"
                    : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <span className={isActive ? "text-indigo-600" : "text-gray-400"}>{icon}</span>
                  {label}
                </>
              )}
            </NavLink>
          ))}

          {/* Reports section */}
          <div className="pt-3 pb-1">
            <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              inReports ? "text-indigo-700" : "text-gray-600"
            }`}>
              <span className={inReports ? "text-indigo-600" : "text-gray-400"}>
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              </span>
              Reports
            </div>

            <div className="ml-4 pl-3 border-l border-gray-200 mt-0.5 space-y-0.5">
              {REPORT_ITEMS.map(({ to, label, disabled }) =>
                disabled ? (
                  <div key={to} className="flex items-center gap-2 px-3 py-1.5 text-xs text-gray-300 cursor-default rounded-lg">
                    {label}
                    <span className="ml-auto text-[10px] bg-gray-100 text-gray-400 px-1.5 py-0.5 rounded">Soon</span>
                  </div>
                ) : (
                  <NavLink
                    key={to}
                    to={to}
                    className={({ isActive }) =>
                      `flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                        isActive
                          ? "bg-indigo-50 text-indigo-700"
                          : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
                      }`
                    }
                  >
                    {label}
                  </NavLink>
                )
              )}
            </div>
          </div>
        </nav>

        {/* User footer */}
        <div className="px-4 py-4 border-t border-gray-200 space-y-2">
          {user && (
            <>
              <div className="flex items-center gap-2">
                <div className="w-7 h-7 rounded-full bg-indigo-100 flex items-center justify-center text-xs font-semibold text-indigo-700 shrink-0">
                  {user.full_name.charAt(0).toUpperCase()}
                </div>
                <div className="min-w-0">
                  <p className="text-xs font-medium text-gray-800 truncate">{user.full_name}</p>
                  <p className="text-xs text-gray-400 truncate">{user.email}</p>
                </div>
              </div>
              <div className="flex items-center justify-between">
                <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${ROLE_BADGE[user.role]}`}>
                  {ROLE_LABEL[user.role]}
                </span>
                <button
                  onClick={logout}
                  className="text-xs text-gray-400 hover:text-gray-700 transition-colors"
                >
                  Sign out
                </button>
              </div>
            </>
          )}
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto">
        {children}
      </main>
    </div>
  );
}
