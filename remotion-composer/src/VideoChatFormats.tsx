import React from "react";
import {
  AbsoluteFill,
  Audio,
  Easing,
  Img,
  OffthreadVideo,
  Sequence,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

const COLORS = {
  ink: "#101316",
  paper: "#F7F6F2",
  white: "#FFFFFF",
  teal: "#1BC5A3",
  coral: "#FF6B57",
  yellow: "#F4C84A",
  blue: "#4F7DFF",
  muted: "#686E72",
};

const FONT = "Arial, Helvetica, sans-serif";

const rise = (frame: number, fps: number, delay = 0) => {
  const value = spring({frame: frame - delay, fps, config: {damping: 18, stiffness: 130}});
  return {opacity: value, transform: `translateY(${interpolate(value, [0, 1], [36, 0])}px)`};
};

const BrandRail: React.FC<{dark?: boolean; label?: string}> = ({dark = false, label = "CONSUMER GUIDE"}) => (
  <div
    style={{
      position: "absolute",
      top: 34,
      left: 36,
      right: 36,
      zIndex: 40,
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      fontFamily: FONT,
      color: dark ? COLORS.white : COLORS.ink,
      fontSize: 20,
      fontWeight: 800,
    }}
  >
    <span>VIDEOCHAT.IM</span>
    <span style={{fontSize: 14, fontWeight: 700, color: dark ? "#CCD2D4" : COLORS.muted}}>{label}</span>
  </div>
);

type CaptionCue = {start: number; end: number; text: string; accent?: string};

const NarrativeCaptions: React.FC<{cues: CaptionCue[]}> = ({cues}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const seconds = frame / fps;
  const cue = cues.find((item) => seconds >= item.start && seconds < item.end);
  if (!cue) return null;
  const local = frame - Math.floor(cue.start * fps);
  const opacity = interpolate(local, [0, 4], [0, 1], {extrapolateRight: "clamp"});
  return (
    <div
      style={{
        position: "absolute",
        left: 34,
        right: 34,
        bottom: 34,
        zIndex: 80,
        backgroundColor: "rgba(16,19,22,0.94)",
        borderLeft: `8px solid ${cue.accent || COLORS.yellow}`,
        color: COLORS.white,
        padding: "20px 22px",
        fontFamily: FONT,
        fontSize: 31,
        lineHeight: 1.16,
        fontWeight: 800,
        opacity,
      }}
    >
      {cue.text}
    </div>
  );
};

const HookScene: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const scale = interpolate(frame, [0, 135], [1.04, 1.14], {extrapolateRight: "clamp", easing: Easing.out(Easing.cubic)});
  return (
    <AbsoluteFill style={{backgroundColor: COLORS.ink, overflow: "hidden"}}>
      <div style={{position: "absolute", top: 92, left: 30, right: 30, height: 590, backgroundColor: COLORS.white, border: `5px solid ${COLORS.white}`, overflow: "hidden"}}>
        <div style={{height: 34, backgroundColor: COLORS.ink, display: "flex", gap: 8, padding: "10px 12px"}}>{[COLORS.coral, COLORS.yellow, COLORS.teal].map((color) => <span key={color} style={{width: 12, height: 12, borderRadius: "50%", backgroundColor: color}} />)}</div>
        <Img src={staticFile("videochat/faceless/home.png")} style={{width: "100%", height: "calc(100% - 34px)", objectFit: "cover", objectPosition: "top", transform: `scale(${scale})`, transformOrigin: "top center"}} />
      </div>
      <BrandRail dark />
      <div style={{position: "absolute", left: 38, right: 38, top: 600, color: COLORS.white, fontFamily: FONT}}>
        <div style={{display: "flex", alignItems: "flex-end", gap: 20}}>
          <div style={{...rise(frame, fps), fontSize: 224, lineHeight: 0.78, fontWeight: 900, color: COLORS.yellow}}>5</div>
          <div style={{...rise(frame, fps, 5), fontSize: 38, lineHeight: 1.03, fontWeight: 900, paddingBottom: 6}}>QUESTIONS<br />BEFORE CAMERA<br />ACCESS</div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

const GoalsScene: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const goals = [
    ["REAL PEOPLE", COLORS.teal, "01"],
    ["RANDOM DISCOVERY", COLORS.coral, "02"],
    ["AI COMPANION", COLORS.blue, "03"],
    ["LANGUAGE PRACTICE", COLORS.yellow, "04"],
  ];
  return (
    <AbsoluteFill style={{backgroundColor: COLORS.paper, color: COLORS.ink, fontFamily: FONT, padding: "118px 38px 190px"}}>
      <BrandRail />
      <div style={{...rise(frame, fps), fontSize: 30, fontWeight: 800, color: COLORS.muted}}>QUESTION 01</div>
      <div style={{...rise(frame, fps, 4), fontSize: 76, lineHeight: 0.96, fontWeight: 900, marginTop: 18}}>WHO DO YOU<br />WANT TO MEET?</div>
      <div style={{marginTop: 62, display: "flex", flexDirection: "column", gap: 16}}>
        {goals.map(([label, color, number], index) => {
          const enter = spring({frame: frame - 10 - index * 6, fps, config: {damping: 18, stiffness: 120}});
          return (
            <div key={label} style={{height: 108, display: "grid", gridTemplateColumns: "74px 1fr 20px", alignItems: "center", borderTop: `2px solid ${COLORS.ink}`, opacity: enter, transform: `translateX(${interpolate(enter, [0, 1], [80, 0])}px)`}}>
              <span style={{fontSize: 22, fontWeight: 900, color}}>{number}</span>
              <span style={{fontSize: 34, fontWeight: 900}}>{label}</span>
              <span style={{width: 14, height: 14, borderRadius: "50%", backgroundColor: color}} />
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

const DeviceScene: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const progress = spring({frame, fps, config: {damping: 16, stiffness: 110}});
  return (
    <AbsoluteFill style={{backgroundColor: COLORS.blue, color: COLORS.white, fontFamily: FONT, padding: "120px 40px 190px"}}>
      <BrandRail dark />
      <div style={{fontSize: 30, fontWeight: 800, opacity: 0.8}}>QUESTION 02</div>
      <div style={{fontSize: 82, lineHeight: 0.96, fontWeight: 900, marginTop: 20}}>BROWSER<br />OR PHONE?</div>
      <div style={{display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 105}}>
        <div style={{width: 390, height: 260, border: "14px solid #FFFFFF", borderRadius: 6, transform: `translateX(${interpolate(progress, [0, 1], [-120, 0])}px)`}}>
          <div style={{height: 34, borderBottom: "8px solid #FFFFFF", display: "flex", gap: 10, alignItems: "center", paddingLeft: 12}}>
            {[0, 1, 2].map((item) => <span key={item} style={{width: 10, height: 10, borderRadius: "50%", backgroundColor: COLORS.yellow}} />)}
          </div>
        </div>
        <div style={{width: 150, height: 300, border: "14px solid #FFFFFF", borderRadius: 28, transform: `translateX(${interpolate(progress, [0, 1], [120, 0])}px)`}}>
          <div style={{width: 54, height: 9, margin: "13px auto", borderRadius: 5, backgroundColor: COLORS.white}} />
        </div>
      </div>
      <div style={{display: "flex", justifyContent: "space-between", marginTop: 32, fontSize: 30, fontWeight: 900}}><span>DESKTOP WEB</span><span>MOBILE</span></div>
    </AbsoluteFill>
  );
};

const FrictionScene: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const move = spring({frame, fps, config: {damping: 20, stiffness: 100}});
  return (
    <AbsoluteFill style={{backgroundColor: COLORS.paper, color: COLORS.ink, fontFamily: FONT, padding: "120px 38px 190px"}}>
      <BrandRail />
      <div style={{fontSize: 30, fontWeight: 800, color: COLORS.muted}}>QUESTION 03</div>
      <div style={{fontSize: 78, lineHeight: 0.96, fontWeight: 900, marginTop: 20}}>HOW MUCH<br />FRICTION?</div>
      <div style={{height: 12, backgroundColor: COLORS.ink, marginTop: 150, position: "relative"}}>
        <div style={{position: "absolute", left: `${interpolate(move, [0, 1], [2, 76])}%`, top: -24, width: 58, height: 58, borderRadius: "50%", backgroundColor: COLORS.coral, border: `8px solid ${COLORS.paper}`}} />
      </div>
      <div style={{display: "flex", justifyContent: "space-between", marginTop: 34, fontSize: 30, fontWeight: 900}}><span>OPEN NOW</span><span>CREATE ACCOUNT</span></div>
      <div style={{marginTop: 120, fontSize: 42, lineHeight: 1.12, fontWeight: 800, maxWidth: 590}}>Convenience is a preference.<br /><span style={{color: COLORS.coral}}>Know the tradeoff.</span></div>
    </AbsoluteFill>
  );
};

const FreeScene: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const strike = interpolate(frame, [18, 55], [0, 100], {extrapolateLeft: "clamp", extrapolateRight: "clamp"});
  return (
    <AbsoluteFill style={{backgroundColor: COLORS.yellow, color: COLORS.ink, fontFamily: FONT, padding: "120px 38px 190px"}}>
      <BrandRail />
      <div style={{fontSize: 30, fontWeight: 800}}>QUESTION 04</div>
      <div style={{fontSize: 160, lineHeight: 0.8, fontWeight: 900, marginTop: 84, position: "relative", width: "max-content"}}>
        FREE
        <span style={{position: "absolute", left: 0, top: "48%", width: `${strike}%`, height: 14, backgroundColor: COLORS.coral}} />
      </div>
      <div style={{...rise(frame, fps, 20), marginTop: 70, fontSize: 48, lineHeight: 1.08, fontWeight: 900}}>A FREE LANDING PAGE<br />IS NOT THE SAME AS<br /><span style={{backgroundColor: COLORS.ink, color: COLORS.white, padding: "3px 10px"}}>A REAL FREE PATH.</span></div>
    </AbsoluteFill>
  );
};

const SafetyScene: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const words = ["BLOCK", "REPORT", "EXIT"];
  return (
    <AbsoluteFill style={{backgroundColor: COLORS.ink, color: COLORS.white, fontFamily: FONT, padding: "120px 38px 190px"}}>
      <BrandRail dark />
      <div style={{fontSize: 30, fontWeight: 800, color: "#BAC1C4"}}>QUESTION 05</div>
      <div style={{fontSize: 72, lineHeight: 0.97, fontWeight: 900, marginTop: 18}}>FIND THESE<br />BEFORE CAMERA ON.</div>
      <div style={{marginTop: 70, display: "flex", flexDirection: "column", gap: 14}}>
        {words.map((word, index) => {
          const p = spring({frame: frame - 8 - index * 8, fps, config: {damping: 16, stiffness: 130}});
          const color = [COLORS.teal, COLORS.yellow, COLORS.coral][index];
          return <div key={word} style={{height: 122, display: "flex", alignItems: "center", paddingLeft: 30, backgroundColor: color, color: COLORS.ink, fontSize: 66, fontWeight: 900, transform: `scaleX(${p})`, transformOrigin: "left center"}}>{word}</div>;
        })}
      </div>
    </AbsoluteFill>
  );
};

const FinderScene: React.FC = () => {
  const frame = useCurrentFrame();
  const zoom = interpolate(frame, [0, 170], [1, 1.12], {extrapolateRight: "clamp"});
  return (
    <AbsoluteFill style={{backgroundColor: COLORS.teal, overflow: "hidden", fontFamily: FONT}}>
      <BrandRail />
      <div style={{position: "absolute", top: 108, left: 34, right: 34, height: 830, backgroundColor: COLORS.white, border: `5px solid ${COLORS.ink}`, overflow: "hidden"}}>
        <div style={{height: 34, backgroundColor: COLORS.ink, display: "flex", gap: 8, padding: "10px 12px"}}>{[COLORS.coral, COLORS.yellow, COLORS.teal].map((c) => <span key={c} style={{width: 12, height: 12, borderRadius: "50%", backgroundColor: c}} />)}</div>
        <Img src={staticFile("videochat/faceless/finder-results.png")} style={{width: "100%", height: "calc(100% - 34px)", objectFit: "cover", objectPosition: "top", transform: `scale(${zoom})`, transformOrigin: "top center"}} />
      </div>
      <div style={{position: "absolute", top: 825, left: 55, right: 55, backgroundColor: COLORS.ink, color: COLORS.white, padding: "24px 26px", fontSize: 38, lineHeight: 1.05, fontWeight: 900}}>COMPARE THE TRADEOFFS<br /><span style={{color: COLORS.teal}}>BEFORE</span> YOU LEAVE.</div>
    </AbsoluteFill>
  );
};

const FastScene: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  return (
    <AbsoluteFill style={{backgroundColor: COLORS.paper, color: COLORS.ink, fontFamily: FONT}}>
      <BrandRail />
      <div style={{position: "absolute", top: 110, left: 0, right: 0, height: 455, backgroundColor: COLORS.coral, padding: "60px 38px"}}>
        <div style={{...rise(frame, fps), fontSize: 96, lineHeight: 0.9, fontWeight: 900}}>FAST<br />ACCESS</div>
        <div style={{marginTop: 24, fontSize: 28, fontWeight: 800}}>CONVENIENT</div>
      </div>
      <div style={{position: "absolute", top: 565, left: 0, right: 0, bottom: 0, backgroundColor: COLORS.teal, padding: "60px 38px"}}>
        <div style={{...rise(frame, fps, 8), fontSize: 96, lineHeight: 0.9, fontWeight: 900}}>SAFETY<br />EVIDENCE</div>
        <div style={{marginTop: 24, fontSize: 28, fontWeight: 800}}>NOT AUTOMATIC</div>
      </div>
    </AbsoluteFill>
  );
};

const EndScene: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  return (
    <AbsoluteFill style={{backgroundColor: COLORS.ink, color: COLORS.white, fontFamily: FONT, alignItems: "center", justifyContent: "center", textAlign: "center", padding: 44}}>
      <div style={{...rise(frame, fps), color: COLORS.yellow, fontSize: 23, fontWeight: 900}}>COMPARE BEFORE YOU CONNECT</div>
      <div style={{...rise(frame, fps, 4), fontSize: 88, lineHeight: 0.92, fontWeight: 900, marginTop: 24}}>CHOOSE THE JOB.<br />THEN CHOOSE<br />THE SITE.</div>
      <div style={{...rise(frame, fps, 9), marginTop: 52, padding: "18px 26px", backgroundColor: COLORS.white, color: COLORS.ink, fontSize: 34, fontWeight: 900}}>VIDEOCHAT.IM</div>
    </AbsoluteFill>
  );
};

const facelessCues: CaptionCue[] = [
  {start: 0.1, end: 4.5, text: "Before you open a random video chat site, answer five questions."},
  {start: 4.7, end: 13.2, text: "Who do you want to meet?", accent: COLORS.teal},
  {start: 13.3, end: 15.6, text: "Are you on a browser or your phone?", accent: COLORS.blue},
  {start: 15.8, end: 20.2, text: "Will you create an account, or start instantly?", accent: COLORS.coral},
  {start: 20.4, end: 24.8, text: "Is it a real free path, or just a free landing page?", accent: COLORS.yellow},
  {start: 24.9, end: 30.7, text: "Find block, report, and exit controls before camera access.", accent: COLORS.coral},
  {start: 30.8, end: 36.2, text: "VideoChat.im compares those tradeoffs before sending you anywhere.", accent: COLORS.teal},
  {start: 36.2, end: 38.7, text: "Fast access is convenient.", accent: COLORS.coral},
  {start: 38.7, end: 40.4, text: "It is not proof of safety.", accent: COLORS.teal},
  {start: 40.5, end: 43.5, text: "Choose the job first. Then choose the site.", accent: COLORS.yellow},
];

export const VideoChatFaceless: React.FC = () => (
  <AbsoluteFill style={{backgroundColor: COLORS.ink}}>
    <Audio src={staticFile("videochat/faceless/music.wav")} loop volume={0.045} />
    <Audio src={staticFile("videochat/faceless/narration.wav")} volume={1} />
    <Sequence from={0} durationInFrames={135}><HookScene /></Sequence>
    <Sequence from={135} durationInFrames={261}><GoalsScene /></Sequence>
    <Sequence from={396} durationInFrames={72}><DeviceScene /></Sequence>
    <Sequence from={468} durationInFrames={138}><FrictionScene /></Sequence>
    <Sequence from={606} durationInFrames={138}><FreeScene /></Sequence>
    <Sequence from={744} durationInFrames={177}><SafetyScene /></Sequence>
    <Sequence from={921} durationInFrames={168}><FinderScene /></Sequence>
    <Sequence from={1089} durationInFrames={123}><FastScene /></Sequence>
    <Sequence from={1212} durationInFrames={93}><EndScene /></Sequence>
    <NarrativeCaptions cues={facelessCues} />
  </AbsoluteFill>
);

type PodcastTurn = {
  id: string;
  speaker: "maya" | "marco";
  from: number;
  duration: number;
  sourceStart: number;
  line: string;
  insert?: "goals" | "safety" | "finder";
};

const podcastTurns: PodcastTurn[] = [
  {id: "t1", speaker: "maya", from: 0, duration: 99, sourceStart: 0, line: "What's the best Omegle alternative right now?"},
  {id: "t2", speaker: "marco", from: 99, duration: 171, sourceStart: 0, line: "That's the wrong first question. Ask who you want to talk to, and how much friction you'll accept.", insert: "goals"},
  {id: "t3", speaker: "maya", from: 270, duration: 95, sourceStart: 99, line: "I just want something free, no signup, and safe."},
  {id: "t4", speaker: "marco", from: 365, duration: 266, sourceStart: 170, line: "Those are three different promises. Find block, report, and exit controls before camera access.", insert: "safety"},
  {id: "t5", speaker: "maya", from: 631, duration: 67, sourceStart: 194, line: "So fastest doesn't mean safest."},
  {id: "t6", speaker: "marco", from: 698, duration: 272, sourceStart: 435, line: "VideoChat.im compares chat type, device, signup, budget, and safety before sending you anywhere.", insert: "finder"},
];

const Waveform: React.FC<{color: string}> = ({color}) => {
  const frame = useCurrentFrame();
  return (
    <div style={{height: 40, display: "flex", alignItems: "center", gap: 5}}>
      {Array.from({length: 28}).map((_, index) => {
        const height = 8 + Math.abs(Math.sin(frame / 3 + index * 0.8)) * 28;
        return <span key={index} style={{display: "block", width: 4, height, backgroundColor: color}} />;
      })}
    </div>
  );
};

const EvidenceInsert: React.FC<{type?: PodcastTurn["insert"]; accent: string}> = ({type, accent}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  if (!type) return <Waveform color={accent} />;
  if (type === "goals") {
    return <div style={{display: "flex", flexWrap: "wrap", gap: 8}}>{["REAL PEOPLE", "RANDOM", "AI", "LANGUAGE"].map((item, index) => <span key={item} style={{...rise(frame, fps, index * 3), padding: "8px 10px", backgroundColor: index === 1 ? COLORS.coral : COLORS.white, color: COLORS.ink, fontSize: 16, fontWeight: 900}}>{item}</span>)}</div>;
  }
  if (type === "safety") {
    return <div style={{display: "flex", gap: 8}}>{["BLOCK", "REPORT", "EXIT"].map((item, index) => <span key={item} style={{...rise(frame, fps, index * 3), flex: 1, padding: "10px 4px", textAlign: "center", backgroundColor: [COLORS.teal, COLORS.yellow, COLORS.coral][index], color: COLORS.ink, fontSize: 18, fontWeight: 900}}>{item}</span>)}</div>;
  }
  return <div style={{fontSize: 18, fontWeight: 900, color: accent}}>CHAT TYPE · DEVICE · SIGNUP · BUDGET · SAFETY</div>;
};

const PodcastTurnScene: React.FC<{turn: PodcastTurn}> = ({turn}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const isMaya = turn.speaker === "maya";
  const accent = isMaya ? COLORS.coral : COLORS.teal;
  const other = isMaya ? "marco" : "maya";
  const showFinder = turn.insert === "finder" && frame > 132;
  return (
    <AbsoluteFill style={{backgroundColor: COLORS.ink, color: COLORS.white, fontFamily: FONT}}>
      <OffthreadVideo
        src={staticFile(`videochat/podcast/${turn.speaker}-master.mp4`)}
        startFrom={turn.sourceStart}
        volume={1}
        style={{position: "absolute", inset: 0, width: "100%", height: 820, objectFit: "cover", objectPosition: "center 22%"}}
      />
      <div style={{position: "absolute", left: 0, right: 0, top: 0, height: 820, borderBottom: `10px solid ${accent}`}} />
      <div style={{position: "absolute", top: 42, left: 34, backgroundColor: accent, color: COLORS.ink, padding: "9px 12px", fontSize: 18, fontWeight: 900}}>AI PODCAST · VIDEOCHAT.IM</div>
      <div style={{position: "absolute", top: 48, right: 34, display: "flex", alignItems: "center", gap: 10, backgroundColor: "rgba(16,19,22,0.82)", padding: 8}}>
        <Img src={staticFile(`videochat/podcast/${other}.png`)} style={{width: 54, height: 54, objectFit: "cover", border: `3px solid ${isMaya ? COLORS.teal : COLORS.coral}`}} />
        <span style={{fontSize: 15, fontWeight: 800}}>{isMaya ? "MARCO · REMOTE" : "MAYA · REMOTE"}</span>
      </div>
      <div style={{position: "absolute", top: 790, left: 34, padding: "12px 18px", backgroundColor: accent, color: COLORS.ink, fontSize: 24, fontWeight: 900}}>{isMaya ? "MAYA" : "MARCO"}</div>
      {turn.id === "t1" && frame < 22 ? (
        <div style={{position: "absolute", inset: "0 0 auto 0", height: 850, display: "flex", zIndex: 20, opacity: interpolate(frame, [15, 22], [1, 0], {extrapolateLeft: "clamp", extrapolateRight: "clamp"})}}>
          <div style={{position: "relative", width: "50%", height: "100%", overflow: "hidden", borderRight: `5px solid ${COLORS.ink}`}}>
            <Img src={staticFile("videochat/podcast/maya.png")} style={{width: "100%", height: "100%", objectFit: "cover", objectPosition: "center"}} />
            <span style={{position: "absolute", left: 20, bottom: 22, backgroundColor: COLORS.coral, color: COLORS.ink, padding: "9px 12px", fontSize: 22, fontWeight: 900}}>MAYA</span>
          </div>
          <div style={{position: "relative", width: "50%", height: "100%", overflow: "hidden"}}>
            <Img src={staticFile("videochat/podcast/marco.png")} style={{width: "100%", height: "100%", objectFit: "cover", objectPosition: "center"}} />
            <span style={{position: "absolute", left: 20, bottom: 22, backgroundColor: COLORS.teal, color: COLORS.ink, padding: "9px 12px", fontSize: 22, fontWeight: 900}}>MARCO</span>
          </div>
          <div style={{position: "absolute", top: 42, left: "50%", transform: "translateX(-50%)", backgroundColor: COLORS.ink, color: COLORS.white, padding: "10px 14px", fontSize: 18, fontWeight: 900}}>AI PODCAST</div>
        </div>
      ) : null}
      <div style={{position: "absolute", top: 850, left: 34, right: 34}}>
        <EvidenceInsert type={turn.insert} accent={accent} />
        <div style={{marginTop: 20, fontSize: 35, lineHeight: 1.08, fontWeight: 900}}>{turn.line}</div>
      </div>
      {showFinder ? (
        <div style={{position: "absolute", top: 110, left: 38, right: 38, height: 655, backgroundColor: COLORS.white, border: `6px solid ${COLORS.teal}`, overflow: "hidden", opacity: interpolate(frame, [132, 142], [0, 1], {extrapolateRight: "clamp"}), transform: `translateY(${interpolate(frame, [132, 142], [30, 0], {extrapolateRight: "clamp"})}px)`}}>
          <Img src={staticFile("videochat/podcast/finder-results.png")} style={{width: "100%", height: "100%", objectFit: "cover", objectPosition: "top"}} />
        </div>
      ) : null}
      <div style={{position: "absolute", bottom: 28, left: 34, right: 34, display: "flex", justifyContent: "space-between", color: "#AEB4B7", fontSize: 15, fontWeight: 800}}><span>CONSUMER QUESTION</span><span>COMPARE BEFORE YOU CONNECT</span></div>
    </AbsoluteFill>
  );
};

export const VideoChatPodcast: React.FC = () => (
  <AbsoluteFill style={{backgroundColor: COLORS.ink}}>
    <Audio src={staticFile("videochat/podcast/music.wav")} loop volume={0.025} />
    {podcastTurns.map((turn) => (
      <Sequence key={turn.id} from={turn.from} durationInFrames={turn.duration}>
        <PodcastTurnScene turn={turn} />
      </Sequence>
    ))}
  </AbsoluteFill>
);
