import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api } from "./api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  // undefined = still checking the session, null = logged out.
  const [user, setUser] = useState(undefined);

  useEffect(() => {
    api.get("/auth/me").then(setUser).catch(() => setUser(null));
    const onExpired = () => setUser(null);
    window.addEventListener("auth:expired", onExpired);
    return () => window.removeEventListener("auth:expired", onExpired);
  }, []);

  const login = useCallback(async (email, password) => {
    setUser(await api.post("/auth/login", { email, password }));
  }, []);

  const register = useCallback(async (email, password, display_name) => {
    setUser(await api.post("/auth/register", { email, password, display_name }));
  }, []);

  const logout = useCallback(async () => {
    await api.post("/auth/logout");
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
