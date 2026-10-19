// Zustand Store for Global State
import { create } from "zustand";

interface User {
  id: number;
  username: string;
  email: string;
  roles: string[];
}

interface AppState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  setUser: (user: User | null) => void;
  setToken: (token: string) => void;
  logout: () => void;
}

const AUTH_DISABLED = process.env.NEXT_PUBLIC_DISABLE_AUTH === "true";
const DEV_USER: User = {
  id: 0,
  username: "local-admin",
  email: "local-admin@localhost",
  roles: ["SUPER_ADMIN", "COLLEGE_ADMIN"],
};

export const useAppStore = create<AppState>((set) => ({
  user: AUTH_DISABLED ? DEV_USER : null,
  token: typeof window !== "undefined" ? localStorage.getItem("access_token") : null,
  isAuthenticated: AUTH_DISABLED
    ? true
    : typeof window !== "undefined"
      ? !!localStorage.getItem("access_token")
      : false,
  setUser: (user) => set({ user, isAuthenticated: !!user }),
  setToken: (token) => {
    if (typeof window !== "undefined") localStorage.setItem("access_token", token);
    set({ token, isAuthenticated: true });
  },
  logout: () => {
    if (typeof window !== "undefined") {
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
    }
    set({ user: null, token: null, isAuthenticated: false });
  },
}));
