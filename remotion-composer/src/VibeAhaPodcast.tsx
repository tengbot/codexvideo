import React from "react";
import {
  AbsoluteFill,
  Audio,
  Img,
  Sequence,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

const COLORS = {
  ink: "#0A0A0A",
  paper: "#F7F6F2",
  coral: "#E4572E",
  teal: "#32C7B5",
  gold: "#F2B544",
  muted: "#AAA7A1",
};

const FONT = "Arial, Helvetica, sans-serif";

type Turn = {
  id: string;
  speaker: "maya" | "marco";
  from: number;
  duration: number;
  line: string;
  audio: string;
  insert?: "compare" | "offer";
};

const turns: Turn[] = [
  {
    id: "turn-01",
    speaker: "maya",
    from: 0,
    duration: 104,
    line: "Why do I need five AI apps just to make one campaign?",
    audio: "vibeaha/podcast/audio/turn-01.wav",
  },
  {
    id: "turn-02",
    speaker: "marco",
    from: 104,
    duration: 205,
    line: "You don't. In VibeAha, you can compare the model, settings, and credit cost before you generate.",
    audio: "vibeaha/podcast/audio/turn-02.wav",
    insert: "compare",
  },
  {
    id: "turn-03",
    speaker: "maya",
    from: 309,
    duration: 103,
    line: "So I stop paying just to discover I picked the wrong model?",
    audio: "vibeaha/podcast/audio/turn-03.wav",
  },
  {
    id: "turn-04",
    speaker: "marco",
    from: 412,
    duration: 224,
    line: "Exactly. One workspace, one credit balance, and no subscription clock. Compare before you create.",
    audio: "vibeaha/podcast/audio/turn-04.wav",
    insert: "offer",
  },
];

const Waveform: React.FC<{color: string}> = ({color}) => {
  const frame = useCurrentFrame();
  return (
    <div style={{height: 38, display: "flex", alignItems: "center", gap: 5}}>
      {Array.from({length: 24}).map((_, index) => {
        const height = 7 + Math.abs(Math.sin(frame / 2.8 + index * 0.74)) * 28;
        return <span key={index} style={{display: "block", width: 4, height, backgroundColor: color}} />;
      })}
    </div>
  );
};

const ProductInsert: React.FC<{type: NonNullable<Turn["insert"]>; accent: string}> = ({type, accent}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const enter = spring({frame: frame - 46, fps, config: {damping: 18, stiffness: 105}});
  const source = type === "compare" ? "vibeaha-model-menu.png" : "vibeaha-video-models.png";
  return (
    <div
      style={{
        position: "absolute",
        left: 34,
        right: 34,
        top: 472,
        height: 310,
        overflow: "hidden",
        border: `5px solid ${accent}`,
        backgroundColor: COLORS.ink,
        opacity: enter,
        transform: `translateY(${interpolate(enter, [0, 1], [46, 0])}px)`,
        boxShadow: "0 20px 50px rgba(0,0,0,0.38)",
      }}
    >
      <Img
        src={staticFile(`vibeaha/podcast/${source}`)}
        style={{width: "100%", height: "100%", objectFit: "cover", objectPosition: type === "compare" ? "center 57%" : "center 48%"}}
      />
      <div style={{position: "absolute", left: 0, right: 0, bottom: 0, padding: "10px 16px", backgroundColor: "rgba(10,10,10,0.86)", color: COLORS.paper, fontSize: 17, fontWeight: 900}}>
        {type === "compare" ? "MODEL · SETTINGS · CREDIT COST" : "ONE WORKSPACE · ONE BALANCE"}
      </div>
    </div>
  );
};

const OpeningSplit: React.FC = () => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [18, 26], [1, 0], {extrapolateLeft: "clamp", extrapolateRight: "clamp"});
  return (
    <div style={{position: "absolute", inset: 0, zIndex: 20, backgroundColor: COLORS.ink, opacity}}>
      <div style={{display: "flex", height: 770}}>
        <div style={{position: "relative", width: "50%", overflow: "hidden", borderRight: `5px solid ${COLORS.ink}`}}>
          <Img src={staticFile("vibeaha/podcast/maya.png")} style={{width: "100%", height: "100%", objectFit: "cover", objectPosition: "51% center"}} />
          <span style={{position: "absolute", left: 18, bottom: 20, backgroundColor: COLORS.coral, color: COLORS.ink, padding: "8px 11px", fontSize: 20, fontWeight: 900}}>MAYA</span>
        </div>
        <div style={{position: "relative", width: "50%", overflow: "hidden"}}>
          <Img src={staticFile("vibeaha/podcast/marco.png")} style={{width: "100%", height: "100%", objectFit: "cover", objectPosition: "50% center"}} />
          <span style={{position: "absolute", right: 18, bottom: 20, backgroundColor: COLORS.teal, color: COLORS.ink, padding: "8px 11px", fontSize: 20, fontWeight: 900}}>MARCO</span>
        </div>
      </div>
      <div style={{padding: "42px 38px", color: COLORS.paper}}>
        <div style={{fontSize: 18, fontWeight: 900, color: COLORS.gold}}>THE CREATOR QUESTION</div>
        <div style={{marginTop: 18, fontSize: 61, lineHeight: 0.96, fontWeight: 900}}>WHY FIVE AI APPS<br />FOR ONE CAMPAIGN?</div>
      </div>
    </div>
  );
};

const SpeakerScene: React.FC<{turn: Turn}> = ({turn}) => {
  const frame = useCurrentFrame();
  const isMaya = turn.speaker === "maya";
  const accent = isMaya ? COLORS.coral : COLORS.teal;
  const other = isMaya ? "marco" : "maya";
  const drift = interpolate(frame, [0, turn.duration], [1.04, 1.1], {extrapolateRight: "clamp"});
  return (
    <AbsoluteFill style={{backgroundColor: COLORS.ink, color: COLORS.paper, fontFamily: FONT, overflow: "hidden"}}>
      <div style={{position: "absolute", left: 0, right: 0, top: 0, height: 805, overflow: "hidden", borderBottom: `9px solid ${accent}`}}>
        <Img
          src={staticFile(`vibeaha/podcast/${turn.speaker}.png`)}
          style={{width: "100%", height: "100%", objectFit: "cover", objectPosition: isMaya ? "center 45%" : "center 40%", transform: `scale(${drift})`}}
        />
        <div style={{position: "absolute", inset: 0, background: "linear-gradient(180deg, rgba(10,10,10,0.04) 42%, rgba(10,10,10,0.78) 100%)"}} />
      </div>

      <div style={{position: "absolute", top: 34, left: 30, padding: "9px 12px", backgroundColor: accent, color: COLORS.ink, fontSize: 17, fontWeight: 900}}>VIBEAHA · CREATOR PODCAST</div>
      <div style={{position: "absolute", top: 34, right: 30, display: "flex", alignItems: "center", gap: 9, padding: 7, backgroundColor: "rgba(10,10,10,0.78)"}}>
        <Img src={staticFile(`vibeaha/podcast/${other}.png`)} style={{width: 52, height: 52, objectFit: "cover", border: `3px solid ${isMaya ? COLORS.teal : COLORS.coral}`}} />
        <span style={{fontSize: 13, fontWeight: 900}}>{isMaya ? "MARCO · LISTENING" : "MAYA · LISTENING"}</span>
      </div>

      <div style={{position: "absolute", left: 32, top: 742, padding: "11px 15px", backgroundColor: accent, color: COLORS.ink, fontSize: 23, fontWeight: 900}}>{isMaya ? "MAYA" : "MARCO"}</div>
      {turn.insert ? <ProductInsert type={turn.insert} accent={accent} /> : null}

      <div style={{position: "absolute", left: 34, right: 34, top: 842}}>
        <Waveform color={accent} />
        <div style={{marginTop: 19, fontSize: turn.line.length > 90 ? 34 : 39, lineHeight: 1.08, fontWeight: 900}}>{turn.line}</div>
      </div>

      <div style={{position: "absolute", left: 34, right: 34, bottom: 26, display: "flex", justifyContent: "space-between", color: COLORS.muted, fontSize: 14, fontWeight: 900}}>
        <span>CREATOR PROBLEM</span><span>COMPARE BEFORE YOU CREATE</span>
      </div>
      {turn.id === "turn-01" ? <OpeningSplit /> : null}
    </AbsoluteFill>
  );
};

const EndCard: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const enter = spring({frame, fps, config: {damping: 18, stiffness: 110}});
  return (
    <AbsoluteFill style={{backgroundColor: COLORS.ink, color: COLORS.paper, fontFamily: FONT, alignItems: "center", justifyContent: "center", textAlign: "center", padding: 42}}>
      <div style={{display: "flex", gap: 12, width: "100%", height: 330, transform: `translateY(${interpolate(enter, [0, 1], [40, 0])}px)`, opacity: enter}}>
        <Img src={staticFile("vibeaha/podcast/maya.png")} style={{width: "50%", objectFit: "cover", objectPosition: "center"}} />
        <Img src={staticFile("vibeaha/podcast/marco.png")} style={{width: "50%", objectFit: "cover", objectPosition: "center"}} />
      </div>
      <Img src={staticFile("vibeaha/podcast/vibeaha-logo.png")} style={{width: 84, height: 84, objectFit: "contain", marginTop: 42}} />
      <div style={{marginTop: 18, color: COLORS.gold, fontSize: 20, fontWeight: 900}}>VIBEAHA</div>
      <div style={{marginTop: 18, fontSize: 66, lineHeight: 0.94, fontWeight: 900}}>COMPARE BEFORE<br />YOU CREATE.</div>
      <div style={{marginTop: 36, backgroundColor: COLORS.coral, color: COLORS.ink, padding: "15px 22px", fontSize: 29, fontWeight: 900}}>VIBEAHA.COM</div>
    </AbsoluteFill>
  );
};

export const VibeAhaPodcast: React.FC = () => (
  <AbsoluteFill style={{backgroundColor: COLORS.ink}}>
    <Audio src={staticFile("vibeaha/podcast/music.wav")} loop volume={0.14} />
    {turns.map((turn) => (
      <Sequence key={turn.id} from={turn.from} durationInFrames={turn.duration}>
        <SpeakerScene turn={turn} />
        <Audio src={staticFile(turn.audio)} volume={1} />
      </Sequence>
    ))}
    <Sequence from={636} durationInFrames={60}>
      <EndCard />
    </Sequence>
  </AbsoluteFill>
);
