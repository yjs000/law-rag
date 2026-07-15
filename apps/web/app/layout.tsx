import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Energy Law Research System",
  description: "국가법령정보 공동활용 Open API 원문 기반 분산에너지 법령 채팅",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="ko"><body>{children}</body></html>;
}
