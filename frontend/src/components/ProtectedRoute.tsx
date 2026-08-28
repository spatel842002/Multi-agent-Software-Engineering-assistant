import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export function ProtectedRoute() {
  const { user, isLoading } = useAuth();

  if (isLoading) return <p className="text-slate-500">Loading...</p>;
  if (!user) return <Navigate to="/login" replace />;
  return <Outlet />;
}
