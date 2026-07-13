import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "에너지 규제 내비게이터",
  description: "국가법령정보센터 원문 기반 분산에너지 법령 조사 워크벤치",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="ko"><body>{children}</body></html>;
}
