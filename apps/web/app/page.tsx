"use client";

import { FormEvent, useEffect, useState } from "react";

type Citation = { id:string; document_title:string; version_label:string; path:string; quote:string; source_url:string };
type Response = { mode:"ai"|"search_only"; summary:string; scope:string; sections:{claim:string; explanation:string; citation_ids:string[]}[]; checklist:{label:string; status:string; citation_ids:string[]}[]; citations:Citation[]; limitations:string[] };
type CorpusStatus = { last_successful_sync:string|null; ai_available:boolean; warnings:string[] };

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function Home() {
  const [question,setQuestion]=useState("분산에너지 사업을 시작할 때 어떤 허가와 신고를 먼저 확인해야 하나요?");
  const [stage,setStage]=useState("planning");
  const [asOf,setAsOf]=useState(new Date().toISOString().slice(0,10));
  const [result,setResult]=useState<Response|null>(null);
  const [loading,setLoading]=useState(false);
  const [error,setError]=useState("");
  const [corpus,setCorpus]=useState<CorpusStatus|null>(null);

  useEffect(()=>{ fetch(`${API}/v1/corpus/status`).then(r=>r.ok?r.json():null).then(setCorpus).catch(()=>setCorpus(null)); },[]);

  async function submit(event:FormEvent){
    event.preventDefault(); setLoading(true); setError("");
    try {
      const response=await fetch(`${API}/v1/questions`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({question,as_of_date:asOf,project_stage:stage})});
      if(!response.ok) throw new Error("요청을 처리하지 못했습니다.");
      setResult(await response.json());
    } catch(e){ setError(e instanceof Error?e.message:"연결 오류"); } finally { setLoading(false); }
  }

  return <main className="shell">
    <header className="topbar"><div className="brand">ENERGY / LAW</div><div className="status">{corpus?.last_successful_sync?`원문 동기화 ${new Date(corpus.last_successful_sync).toLocaleDateString("ko-KR")}`:"국가법령정보센터 원문 전용"}</div></header>
    <section className="hero"><div className="eyebrow">Distributed energy legal research</div><h1>규제의 경로를<br/>근거까지 추적합니다.</h1><p>일반적인 챗봇처럼 그럴듯한 결론을 만들지 않습니다. 질문 기준일의 법률·시행령·시행규칙·고시를 연결하고, 모든 핵심 주장 옆에 조문 원문을 붙입니다.</p></section>
    <section className="workspace">
      <form className="panel" onSubmit={submit}>
        <div className="panel-head"><strong>사업 질문</strong><span className="mode">RAG WORKBENCH</span></div>
        <div className="panel-body">
          <label className="label" htmlFor="question">무엇을 확인할까요?</label>
          <textarea id="question" value={question} onChange={e=>setQuestion(e.target.value)} maxLength={2000}/>
          <div className="filters"><div><label className="label" htmlFor="stage">사업 단계</label><select id="stage" value={stage} onChange={e=>setStage(e.target.value)}><option value="planning">기획</option><option value="permitting">인허가</option><option value="construction">시공</option><option value="operation">운영</option><option value="change">변경</option></select></div><div><label className="label" htmlFor="date">법령 기준일</label><input id="date" type="date" value={asOf} onChange={e=>setAsOf(e.target.value)}/></div></div>
          <button className="ask" disabled={loading}>{loading?"근거를 찾는 중…":"법령 근거 조사"}</button>
          {error&&<div className="notice">{error}</div>}
          <div className="notice">이 서비스는 법률 자문을 대체하지 않습니다. 현재 MVP 허용 목록만 검색합니다.</div>
        </div>
      </form>
      <article className="panel">
        <div className="panel-head"><strong>검증된 답변</strong>{result&&<span className="mode">{result.mode==="ai"?"AI + 인용 검증":"검색 전용"}</span>}</div>
        {!result?<div className="result-empty">질문을 입력하면 답변과<br/>조문 원문을 함께 표시합니다.</div>:<div className="panel-body"><p className="summary">{result.summary}</p>{result.sections.map((section,i)=><section className="claim" key={i}><h3>{section.claim}{section.citation_ids.map(id=><button className="cite" key={id}>{id}</button>)}</h3><p>{section.explanation}</p></section>)}{result.checklist.length>0&&<section className="claim"><h3>사업 단계 체크리스트</h3>{result.checklist.map((item,i)=><p key={i}>□ {item.label} {item.citation_ids.map(id=><button className="cite" key={id}>{id}</button>)}</p>)}</section>}<section className="claim"><h3>범위와 한계</h3>{result.limitations.map((item,i)=><p key={i}>· {item}</p>)}</section></div>}
      </article>
      {result&&<aside className="panel" style={{gridColumn:"1 / -1"}}><div className="panel-head"><strong>원문 근거</strong><small>{result.scope}</small></div><div className="panel-body">{result.citations.map(c=><div className="source" key={c.id}><strong>{c.id} · {c.document_title} {c.path}</strong><small>{c.version_label}</small><blockquote>{c.quote}</blockquote></div>)}</div></aside>}
    </section>
  </main>;
}
