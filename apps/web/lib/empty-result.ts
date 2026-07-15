import type { QuestionResponse } from "./contracts";

export type EmptyResultMessage = {
  title: string;
  reason: string;
  guidance: string;
};

const BARE_PROVISION_REFERENCE = /^\s*(?:제\s*)?\d+\s*조(?:\s*(?:의\s*\d+))?(?:\s*(?:제\s*)?\d+\s*항)?(?:\s*(?:은|는|이|가|을|를))?\s*[?？.]?\s*$/;

export function getEmptyResultMessage(
  response: QuestionResponse,
  question: string,
): EmptyResultMessage | null {
  const hasNoResults = response.result_status === "no_results"
    || (response.result_status !== "results"
      && response.sections.length === 0
      && response.citations.length === 0);

  if (!hasNoResults) return null;

  const apiReason = response.no_results_reason?.trim();
  const isBareProvisionReference = BARE_PROVISION_REFERENCE.test(question);
  const reason = apiReason === "requested_path_not_found"
    ? "요청한 조·항 경로를 기준일에 유효한 MVP 대상 법령에서 찾지 못했습니다."
    : apiReason === "no_matching_evidence"
      ? "기준일에 유효한 MVP 법령 범위에서 질문과 일치하는 조문을 찾지 못했습니다."
      : isBareProvisionReference
        ? "기존 검색 응답에서 조문 번호와 일치하는 원문이 반환되지 않았습니다."
        : "기준일에 유효한 MVP 법령 범위에서 질문과 일치하는 조문을 찾지 못했습니다.";

  return {
    title: "검색 결과가 없습니다",
    reason,
    guidance: isBareProvisionReference
      ? "법령명과 조문 번호를 함께 적어 주세요. 예: 전기사업법 제1조 제2항은?"
      : "법령명, 사업 단계, 허가·신고 등 확인하려는 쟁점을 포함해 질문을 구체화해 주세요.",
  };
}
