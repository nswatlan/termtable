import { useEffect, useState } from "react";
import { Navigate, NavLink, Route, Routes, useLocation } from "react-router-dom";
import { api } from "./api";
import { useAuth } from "./auth";
import Assignments from "./pages/Assignments";
import Calendar from "./pages/Calendar";
import CourseDetail from "./pages/CourseDetail";
import Courses from "./pages/Courses";
import GradeDetail from "./pages/GradeDetail";
import Grades from "./pages/Grades";
import Login from "./pages/Login";
import Planner from "./pages/Planner";
import Reviews from "./pages/Reviews";

// Count of event invitations waiting for an answer, shown on the Calendar tab.
function usePendingInvites() {
  const [count, setCount] = useState(0);
  const location = useLocation();
  useEffect(() => {
    const refresh = () => api.get("/invitations/count").then((r) => setCount(r.pending)).catch(() => {});
    refresh();
    window.addEventListener("invitations:changed", refresh);
    return () => window.removeEventListener("invitations:changed", refresh);
  }, [location.pathname]);
  return count;
}

function RequireAuth({ children }) {
  const { user } = useAuth();
  const location = useLocation();
  if (user === undefined) return <div className="page-loading">Loading…</div>;
  if (user === null) return <Navigate to="/login" replace state={{ from: location }} />;
  return children;
}

function Shell({ children }) {
  const { user, logout } = useAuth();
  const pendingInvites = usePendingInvites();
  return (
    <div className="shell">
      <header className="topbar">
        <NavLink to="/planner" className="brand">
          <span className="brand-mark">▦</span> Termtable
        </NavLink>
        <nav className="topnav">
          <NavLink to="/planner">Planner</NavLink>
          <NavLink to="/courses">Courses</NavLink>
          <NavLink to="/calendar">
            Calendar
            {pendingInvites > 0 && (
              <span className="count-badge" title={`${pendingInvites} invitation${pendingInvites === 1 ? "" : "s"} waiting`}>
                {pendingInvites}
              </span>
            )}
          </NavLink>
          <NavLink to="/assignments">Assignments</NavLink>
          <NavLink to="/grades">Grades</NavLink>
          <NavLink to="/reviews">Reviews</NavLink>
        </nav>
        <div className="topbar-user">
          <span className="muted">{user.display_name}</span>
          <button className="btn btn-ghost btn-sm" onClick={logout}>Log out</button>
        </div>
      </header>
      <main className="main">{children}</main>
    </div>
  );
}

const authed = (element) => (
  <RequireAuth>
    <Shell>{element}</Shell>
  </RequireAuth>
);

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/planner" element={authed(<Planner />)} />
      <Route path="/courses" element={authed(<Courses />)} />
      <Route path="/courses/:courseId" element={authed(<CourseDetail />)} />
      <Route path="/calendar" element={authed(<Calendar />)} />
      <Route path="/assignments" element={authed(<Assignments />)} />
      <Route path="/reviews" element={authed(<Reviews />)} />
      <Route path="/grades" element={authed(<Grades />)} />
      <Route path="/grades/:termId/:courseId" element={authed(<GradeDetail />)} />
      <Route path="*" element={<Navigate to="/planner" replace />} />
    </Routes>
  );
}
