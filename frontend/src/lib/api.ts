import axios, { type AxiosInstance } from "axios";

export class EmergeError extends Error {
  code: string;
  status: number;
  constructor(code: string, message: string, status: number) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

export const api: AxiosInstance = axios.create({ baseURL: "" });

export function setAuthToken(token: string | null) {
  if (token) api.defaults.headers.common.Authorization = `Bearer ${token}`;
  else delete api.defaults.headers.common.Authorization;
}

api.interceptors.response.use(
  (resp) => resp,
  (err) => {
    const data = err?.response?.data;
    if (
      data &&
      typeof data === "object" &&
      "error_code" in data &&
      "error_message_en" in data
    ) {
      return Promise.reject(
        new EmergeError(
          String(data.error_code),
          String(data.error_message_en),
          err.response.status ?? 500,
        ),
      );
    }
    return Promise.reject(err);
  },
);
