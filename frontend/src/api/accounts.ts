// /api/auth and /api/account. The session cookie (haki_auth, HttpOnly) is sent automatically; nothing is kept in JS.
import { JSON_HEADERS, parse } from "./client";

export interface User {
  id: string;
  username: string;
  display_name: string;
}

export interface Me {
  user: User | null;
  locked: boolean;
  lock_in_s: number;
}

export interface AuthResult {
  user: User;
  recovery_code: string | null;
}

export interface Profile {
  name: string;
  address: string;
  phone: string;
  email: string;
  id_number: string;
}

export interface Prefs {
  save_history: boolean;
  auto_lock_minutes: number;
}

async function send<T>(method: string, path: string, body?: unknown): Promise<T> {
  const init: RequestInit = { method, headers: JSON_HEADERS };
  if (body !== undefined) init.body = JSON.stringify(body);
  return parse<T>(await fetch(path, init));
}

/** Who is signed in; active=true also reports user activity (resets the idle auto-lock). */
export const getMe = async (active = false): Promise<Me> =>
  parse<Me>(await fetch(active ? "/api/auth/me?active=true" : "/api/auth/me"));

export const register = (username: string, password: string, display_name: string) =>
  send<AuthResult>("POST", "/api/auth/register", { username, password, display_name });
export const login = (username: string, password: string) =>
  send<AuthResult>("POST", "/api/auth/login", { username, password });
export const logout = () => send<Me>("POST", "/api/auth/logout");
export const lock = () => send<Me>("POST", "/api/auth/lock");
export const unlock = (password: string) => send<AuthResult>("POST", "/api/auth/unlock", { password });
export const recover = (username: string, recovery_code: string, new_password: string) =>
  send<AuthResult>("POST", "/api/auth/recover", { username, recovery_code, new_password });
export const changePassword = (current_password: string, new_password: string) =>
  send<Me>("POST", "/api/auth/password", { current_password, new_password });

export const getProfile = () => send<Profile>("GET", "/api/account/profile");
export const putProfile = (profile: Profile) => send<Profile>("PUT", "/api/account/profile", profile);
export const getPrefs = () => send<Prefs>("GET", "/api/account/prefs");
export const putPrefs = (prefs: Prefs) => send<Prefs>("PUT", "/api/account/prefs", prefs);
export const deleteAccount = (password: string) => send<Me>("DELETE", "/api/account", { password });

/** Download URL of the decrypted account export (same-origin GET; the cookie authorises it). */
export const EXPORT_URL = "/api/account/export";
