import React from "react";
import {
  AbsoluteFill,
  Audio,
  Easing,
  Img,
  Sequence,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { CameraMotionBlur } from "@remotion/motion-blur";

export const VIBEAHA_SHOTCRAFT_FRAMES = 675;

const W = 720;
const H = 1280;
const GOLD = "#e8bd63";
const ORANGE = "#c63f0b";
const BLUE = "#4aa8e8";
const GREEN = "#36bd88";
const INK = "#101010";
const PAPER = "#f4f1eb";
const MUTED = "#a9a9a9";
const FONT = "Arial, Helvetica, sans-serif";

const clamp01 = (value: number) => Math.max(0, Math.min(1, value));
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;

const Grain: React.FC<{ light?: boolean }> = ({ light = false }) => (
  <AbsoluteFill
    style={{
      pointerEvents: "none",
      opacity: light ? 0.035 : 0.055,
      mixBlendMode: light ? "multiply" : "screen",
      backgroundImage:
        "repeating-linear-gradient(0deg, transparent 0px, transparent 2px, rgba(255,255,255,.32) 3px), repeating-linear-gradient(90deg, transparent 0px, transparent 3px, rgba(0,0,0,.22) 4px)",
    }}
  />
);

const Chrome: React.FC<{ children: React.ReactNode; label?: string }> = ({ children, label }) => (
  <div
    style={{
      width: "100%",
      height: "100%",
      borderRadius: 18,
      overflow: "hidden",
      background: "#0a0a0a",
      border: "1px solid rgba(255,255,255,.15)",
      boxShadow: "0 28px 90px rgba(0,0,0,.35)",
    }}
  >
    <div
      style={{
        height: 42,
        padding: "0 16px",
        display: "flex",
        alignItems: "center",
        gap: 7,
        background: "#171717",
        borderBottom: "1px solid rgba(255,255,255,.1)",
      }}
    >
      {["#ff6b57", "#f0be4b", "#46c960"].map((color) => (
        <div key={color} style={{ width: 10, height: 10, borderRadius: 10, background: color }} />
      ))}
      {label ? (
        <div style={{ marginLeft: "auto", color: "#d6d6d6", font: `700 12px ${FONT}`, letterSpacing: 0 }}>
          {label}
        </div>
      ) : null}
    </div>
    <div style={{ position: "relative", height: "calc(100% - 42px)", overflow: "hidden" }}>{children}</div>
  </div>
);

// Adapted from video-shotcraft crash-zoom-punch / CrashZoomReal.tsx.
const HookCanvas: React.FC = () => {
  const frame = useCurrentFrame();
  const enter = spring({ frame, fps: 30, config: { damping: 18, stiffness: 120 } });
  const zoom = interpolate(frame, [34, 40, 47], [1, 2.58, 2.42], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.55, 0, 0.7, 1),
  });
  const modelNames = [
    ["SEEDANCE 2.0", BLUE, -2],
    ["VEO 3.1 FAST", GREEN, 3],
    ["GROK IMAGINE", "#eb6e55", -4],
    ["MINIMAX H3", "#b68cf2", 2],
    ["GEMINI OMNI", GOLD, -3],
    ["KLING 3.0", "#f28caf", 4],
  ] as const;

  return (
    <AbsoluteFill style={{ background: PAPER, overflow: "hidden", fontFamily: FONT }}>
      <div
        style={{
          position: "absolute",
          inset: 0,
          transform: `scale(${zoom})`,
          transformOrigin: "360px 770px",
        }}
      >
        <div style={{ position: "absolute", left: 46, top: 76, fontSize: 16, fontWeight: 800, color: ORANGE, letterSpacing: 2 }}>
          ONE IDEA. TOO MANY MODELS.
        </div>
        <div
          style={{
            position: "absolute",
            left: 42,
            top: 118,
            width: 640,
            color: INK,
            fontSize: 76,
            lineHeight: 0.98,
            fontWeight: 900,
            letterSpacing: 0,
            transform: `translateY(${(1 - enter) * 70}px)`,
            opacity: enter,
          }}
        >
          STILL
          <br />
          GUESSING?
        </div>
        <div style={{ position: "absolute", left: 44, top: 306, fontSize: 25, color: "#4a4a4a", fontWeight: 700 }}>
          Which AI model actually fits?
        </div>

        <div style={{ position: "absolute", left: 38, top: 400, width: 644, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          {modelNames.map(([name, color, tilt], index) => {
            const chip = spring({ frame: frame - index * 3, fps: 30, config: { damping: 14, stiffness: 145, mass: 0.8 } });
            return (
              <div
                key={name}
                style={{
                  height: 76,
                  display: "flex",
                  alignItems: "center",
                  padding: "0 20px",
                  border: `2px solid ${INK}`,
                  background: color,
                  color: INK,
                  fontSize: 18,
                  fontWeight: 900,
                  transform: `translateY(${(1 - chip) * (90 + index * 8)}px) rotate(${tilt * (1 - chip)}deg)`,
                  opacity: chip,
                  boxShadow: "7px 7px 0 #101010",
                }}
              >
                {name}
              </div>
            );
          })}
        </div>

        <div
          style={{
            position: "absolute",
            left: 190,
            top: 700,
            width: 340,
            height: 154,
            border: `4px solid ${INK}`,
            background: "#ffffff",
            boxShadow: "12px 12px 0 #101010",
            display: "flex",
            flexDirection: "column",
            justifyContent: "center",
            alignItems: "center",
          }}
        >
          <div style={{ fontSize: 17, fontWeight: 900, letterSpacing: 2, color: ORANGE }}>COST UNKNOWN</div>
          <div style={{ fontSize: 72, lineHeight: 0.9, fontWeight: 900, color: INK }}>?</div>
        </div>
      </div>
      <Grain light />
    </AbsoluteFill>
  );
};

const HookScene: React.FC = () => {
  const frame = useCurrentFrame();
  return frame >= 32 && frame <= 44 ? (
    <CameraMotionBlur shutterAngle={200} samples={20}>
      <HookCanvas />
    </CameraMotionBlur>
  ) : (
    <HookCanvas />
  );
};

// Adapted from video-shotcraft brand-frame-snap / BrandFrameSnap.tsx.
const WorkspaceScene: React.FC = () => {
  const frame = useCurrentFrame();
  const drop = spring({ frame: Math.max(0, frame - 12), fps: 30, config: { damping: 16, stiffness: 110, mass: 1 } });
  const frameGrow = 26 * (1 - Math.pow(1 - clamp01(frame / 18), 3));
  const windowY = interpolate(drop, [0, 1], [540, 0]);
  const windowScale = interpolate(drop, [0, 1], [0.84, 1]);
  const pan = interpolate(frame, [36, 124], [-72, -305], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.inOut(Easing.cubic) });
  const copyIn = spring({ frame: Math.max(0, frame - 22), fps: 30, config: { damping: 18, stiffness: 105 } });

  return (
    <AbsoluteFill style={{ background: INK, color: "#fff", fontFamily: FONT, overflow: "hidden" }}>
      <div style={{ position: "absolute", inset: frameGrow, background: "#111", overflow: "hidden" }}>
        <div style={{ position: "absolute", left: 42, top: 62, fontSize: 16, color: GOLD, fontWeight: 900, letterSpacing: 2 }}>
          VIBEAHA
        </div>
        <div
          style={{
            position: "absolute",
            left: 40,
            top: 106,
            width: 640,
            fontSize: 65,
            lineHeight: 0.98,
            fontWeight: 900,
            letterSpacing: 0,
            opacity: copyIn,
            transform: `translateY(${(1 - copyIn) * 42}px)`,
          }}
        >
          ONE
          <br />
          WORKSPACE.
        </div>

        <div
          style={{
            position: "absolute",
            left: 48,
            top: 296,
            width: 624,
            height: 650,
            transform: `translateY(${windowY}px) scale(${windowScale})`,
            transformOrigin: "50% 55%",
            opacity: interpolate(drop, [0, 0.18], [0, 1], { extrapolateRight: "clamp" }),
          }}
        >
          <Chrome label="CREATIVE STUDIO">
            <Img
              src={staticFile("vibeaha/shotcraft/app.png")}
              style={{ position: "absolute", width: 960, height: 540, maxWidth: "none", left: pan, top: 0 }}
            />
            <div
              style={{
                position: "absolute",
                left: 20,
                right: 20,
                bottom: 18,
                height: 54,
                display: "flex",
                alignItems: "center",
                justifyContent: "space-around",
                background: "rgba(10,10,10,.9)",
                border: "1px solid rgba(255,255,255,.13)",
                color: "#fff",
                fontSize: 14,
                fontWeight: 900,
              }}
            >
              <span>IMAGE</span><span style={{ color: GOLD }}>VIDEO</span><span>FINISHING</span>
            </div>
          </Chrome>
        </div>
        <div style={{ position: "absolute", left: 48, bottom: 78, display: "flex", gap: 9 }}>
          {["ONE ACCOUNT", "ONE BALANCE", "LESS SWITCHING"].map((label, index) => {
            const p = spring({ frame: Math.max(0, frame - 52 - index * 6), fps: 30, config: { damping: 16, stiffness: 130 } });
            return (
              <div key={label} style={{ padding: "13px 15px", background: index === 1 ? GOLD : "#242424", color: index === 1 ? INK : "#fff", fontSize: 12, fontWeight: 900, opacity: p, transform: `translateY(${(1 - p) * 24}px)` }}>
                {label}
              </div>
            );
          })}
        </div>
      </div>
      {[
        { left: 0, top: 0, right: 0, height: frameGrow },
        { left: 0, bottom: 0, right: 0, height: frameGrow },
        { left: 0, top: 0, bottom: 0, width: frameGrow },
        { right: 0, top: 0, bottom: 0, width: frameGrow },
      ].map((position, index) => <div key={index} style={{ position: "absolute", background: GOLD, ...position }} />)}
      <Grain />
    </AbsoluteFill>
  );
};

// Adapted from video-shotcraft graze-face-tour / GrazeFaceTour.tsx.
const GrazeProofScene: React.FC = () => {
  const frame = useCurrentFrame();
  const t = clamp01(frame / 96);
  const planeX = interpolate(t, [0, 1], [-130, -460], { easing: Easing.bezier(0.45, 0, 0.25, 1) });
  const planeY = interpolate(t, [0, 1], [485, 360], { easing: Easing.bezier(0.45, 0, 0.25, 1) });
  const landing = (index: number) => {
    const p = clamp01((t - (0.18 + index * 0.17)) / 0.28);
    return (1 - Easing.bezier(0.5, 0.05, 0.6, 1)(p)) * 110;
  };
  const callouts = [
    { label: "MODEL", value: "GPT IMAGE 2", x: 58, y: 886, color: BLUE },
    { label: "SETTINGS", value: "AUTO · 1K", x: 302, y: 960, color: GOLD },
    { label: "CREDIT COST", value: "3 CREDITS", x: 98, y: 1050, color: GREEN },
  ];

  return (
    <AbsoluteFill style={{ background: "#e9e5dc", color: INK, fontFamily: FONT, overflow: "hidden", perspective: 900 }}>
      <div style={{ position: "absolute", left: 40, top: 56, fontSize: 16, color: ORANGE, fontWeight: 900, letterSpacing: 2 }}>
        SEE IT BEFORE YOU SPEND
      </div>
      <div style={{ position: "absolute", left: 38, top: 96, width: 640, fontSize: 58, fontWeight: 900, lineHeight: 1.02 }}>
        MODEL. SETTINGS.
        <br />
        CREDIT COST.
      </div>
      <div
        style={{
          position: "absolute",
          left: planeX,
          top: planeY,
          width: 1220,
          height: 686,
          transform: "rotateX(9deg) rotateY(-13deg) rotateZ(-3deg)",
          transformOrigin: "50% 40%",
          boxShadow: "0 60px 110px rgba(0,0,0,.3)",
          border: "2px solid rgba(255,255,255,.18)",
          overflow: "hidden",
          background: "#0b0b0b",
        }}
      >
        <Img src={staticFile("vibeaha/shotcraft/model-menu.png")} style={{ width: 1220, height: 686 }} />
      </div>
      {callouts.map((item, index) => {
        const lift = landing(index);
        return (
          <div key={item.label} style={{ position: "absolute", left: item.x, top: item.y - lift, width: 290, height: 78 }}>
            {lift > 2 ? <div style={{ position: "absolute", inset: 0, transform: `translate(${lift * 0.16}px, ${lift * 0.34}px)`, filter: `blur(${4 + lift * 0.05}px)`, opacity: 0.24, background: INK }} /> : null}
            <div style={{ position: "absolute", inset: 0, padding: "12px 15px", border: `2px solid ${INK}`, background: item.color, boxShadow: "6px 6px 0 #101010" }}>
              <div style={{ fontSize: 11, fontWeight: 900, letterSpacing: 1.5 }}>{item.label}</div>
              <div style={{ marginTop: 5, fontSize: 19, fontWeight: 900 }}>{item.value}</div>
            </div>
          </div>
        );
      })}
      <Grain light />
    </AbsoluteFill>
  );
};

// Adapted from video-shotcraft transition-travel / SharedElementMorph.tsx.
const ModelMorphScene: React.FC = () => {
  const frame = useCurrentFrame();
  const morphStart = 18;
  const morphEnd = 43;
  const settleEnd = 53;
  const drive = interpolate(frame, [morphStart, morphEnd], [0, 1.03], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.4, 0, 0.2, 1),
  });
  const settle = interpolate(frame, [morphEnd, settleEnd], [1.03, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });
  const p = frame <= morphEnd ? drive : settle;
  const full = { x: 0, y: 320, w: 720, h: 405, r: 0 };
  const slot = { x: 66, y: 830, w: 588, h: 331, r: 18 };
  const x = lerp(full.x, slot.x, p);
  const y = lerp(full.y, slot.y, p);
  const w = lerp(full.w, slot.w, p);
  const h = lerp(full.h, slot.h, p);
  const radius = lerp(full.r, slot.r, p);
  const bgOpacity = interpolate(frame, [morphEnd - 5, morphEnd + 5], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const scale = w / 720;

  return (
    <AbsoluteFill style={{ background: "#0b0b0b", color: "#fff", fontFamily: FONT, overflow: "hidden" }}>
      <div style={{ opacity: bgOpacity }}>
        <div style={{ position: "absolute", left: 42, top: 62, color: GOLD, fontWeight: 900, fontSize: 15, letterSpacing: 2 }}>IMAGE → VIDEO</div>
        <div style={{ position: "absolute", left: 40, top: 105, width: 640, fontSize: 58, lineHeight: 1.02, fontWeight: 900 }}>
          SIX VIDEO MODELS.
          <br />
          ONE CLEAR VIEW.
        </div>
        <div style={{ position: "absolute", left: 40, top: 310, width: 640, height: 360 }}>
          <Chrome label="VIDEO MODELS">
            <Img src={staticFile("vibeaha/shotcraft/video-models.png")} style={{ position: "absolute", width: 640, height: 360 }} />
          </Chrome>
        </div>
        <div style={{ position: "absolute", left: 40, top: 715, right: 40, display: "flex", justifyContent: "space-between", color: MUTED, fontSize: 12, fontWeight: 900 }}>
          <span style={{ color: BLUE }}>SEEDANCE</span><span>VEO</span><span>GROK</span><span>MINIMAX</span><span>GEMINI</span><span>KLING</span>
        </div>
      </div>

      <div style={{ position: "absolute", left: x, top: y, width: w, height: h, borderRadius: radius, overflow: "hidden", boxShadow: `0 ${lerp(38, 5, clamp01(p))}px ${lerp(100, 24, clamp01(p))}px rgba(0,0,0,.42)`, border: "1px solid rgba(255,255,255,.16)" }}>
        <div style={{ width: 720, height: 405, transform: `scale(${scale})`, transformOrigin: "top left" }}>
          <Img src={staticFile("vibeaha/shotcraft/model-menu.png")} style={{ width: 720, height: 405 }} />
        </div>
      </div>
      <Grain />
    </AbsoluteFill>
  );
};

type TimedLineProps = { words: string[]; start: number; end: number; active: boolean; color: string };

// Adapted from video-shotcraft type-rhythm-sync / KaraokeFillSync.tsx.
const TimedLine: React.FC<TimedLineProps> = ({ words, start, end, active, color }) => {
  const frame = useCurrentFrame();
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 12, opacity: active ? 1 : 0.25 }}>
      {words.map((word, index) => {
        const wordStart = start + ((end - start) / words.length) * index;
        const wordEnd = start + ((end - start) / words.length) * (index + 1);
        const p = interpolate(frame, [wordStart, wordEnd], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
        return (
          <span key={word} style={{ position: "relative", display: "inline-block", color: "#555" }}>
            {word}
            <span style={{ position: "absolute", inset: 0, color, clipPath: `inset(0 ${(1 - p) * 100}% 0 0)` }}>{word}</span>
          </span>
        );
      })}
    </div>
  );
};

const OfferScene: React.FC = () => {
  const frame = useCurrentFrame();
  const phase = frame < 27 ? 0 : frame < 57 ? 1 : 2;
  const colors = [GOLD, BLUE, GREEN];
  const frameColor = colors[phase];
  const sinceFlip = phase === 0 ? frame : phase === 1 ? frame - 27 : frame - 57;
  const flash = sinceFlip >= 0 && sinceFlip < 3 && frame > 0 ? 0.35 - sinceFlip * 0.11 : 0;
  const pulse = sinceFlip >= 0 ? Math.exp(-sinceFlip * 0.22) * Math.cos(sinceFlip * 0.9) * 5 : 0;
  const pricingY = interpolate(frame, [0, 145], [680, 625], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.inOut(Easing.cubic) });

  return (
    <AbsoluteFill style={{ background: INK, color: "#fff", fontFamily: FONT, overflow: "hidden" }}>
      <div style={{ position: "absolute", inset: 22 + pulse, border: `8px solid ${frameColor}`, overflow: "hidden" }}>
        <div style={{ position: "absolute", left: 34, top: 50, fontSize: 15, fontWeight: 900, color: frameColor, letterSpacing: 2 }}>PAY ON YOUR SCHEDULE</div>
        <div style={{ position: "absolute", left: 34, top: 105, right: 28, display: "flex", flexDirection: "column", gap: 25, fontSize: 45, lineHeight: 1, fontWeight: 900 }}>
          <TimedLine words={["ONE", "BALANCE."]} start={0} end={23} active={phase === 0} color={GOLD} />
          <TimedLine words={["NO", "SUBSCRIPTION."]} start={26} end={52} active={phase === 1} color={BLUE} />
          <TimedLine words={["CREDITS", "NEVER", "EXPIRE."]} start={57} end={108} active={phase === 2} color={GREEN} />
        </div>
        <div style={{ position: "absolute", left: -20, top: pricingY, width: 760, height: 428, transform: "rotateX(3deg) rotateZ(-1.5deg)", boxShadow: "0 30px 90px rgba(0,0,0,.55)" }}>
          <Img src={staticFile("vibeaha/shotcraft/pricing.png")} style={{ width: 760, height: 428 }} />
        </div>
        <div style={{ position: "absolute", left: 35, bottom: 43, color: "#b8b8b8", fontSize: 14, fontWeight: 700 }}>
          ONE-TIME CREDIT PACKS · VIBEAHA.COM
        </div>
      </div>
      {flash > 0 ? <AbsoluteFill style={{ background: "#fff", opacity: flash }} /> : null}
      <Grain />
    </AbsoluteFill>
  );
};

// Adapted from video-shotcraft ui-to-brand-morph / InputMorphsIntoLogo.tsx.
const CtaScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const click = 22;
  const fly = 26;
  const morphStart = 34;
  const box0 = { x: 50, y: 338, w: 620, h: 104, r: 18 };
  const finalBox = { x: 274, y: 320, w: 172, h: 172, r: 48 };
  const cursorX = interpolate(frame, [0, click], [650, 612], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) });
  const cursorY = interpolate(frame, [0, click], [610, 388], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) });
  const flyT = interpolate(frame, [fly, fly + 12], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.in(Easing.cubic) });
  const morph = spring({ frame: Math.max(0, frame - morphStart), fps, config: { damping: 13, stiffness: 90, mass: 0.9 } });
  const ctaIn = spring({ frame: Math.max(0, frame - 70), fps, config: { damping: 16, stiffness: 105 } });
  const cursorOpacity = interpolate(frame, [fly + 4, fly + 12], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const drops = [
    { start: 54, x: 210, y: 310, w: 56, h: 120, color: BLUE },
    { start: 66, x: 454, y: 352, w: 94, h: 46, color: GREEN },
    { start: 78, x: 430, y: 500, w: 42, h: 42, color: ORANGE },
  ];

  return (
    <AbsoluteFill style={{ background: "#0a0a0a", color: "#fff", fontFamily: FONT, overflow: "hidden" }}>
      <div style={{ position: "absolute", left: 42, top: 68, color: GOLD, fontWeight: 900, fontSize: 15, letterSpacing: 2 }}>FROM QUESTION TO CREATION</div>
      <div
        style={{
          position: "absolute",
          left: lerp(box0.x, finalBox.x, morph),
          top: lerp(box0.y, finalBox.y, morph),
          width: lerp(box0.w, finalBox.w, morph),
          height: lerp(box0.h, finalBox.h, morph),
          borderRadius: lerp(box0.r, finalBox.r, morph),
          border: `3px solid ${GOLD}`,
          background: `rgba(232,189,99,${morph * 0.11})`,
          boxShadow: morph > 0.55 ? "0 0 80px rgba(232,189,99,.25)" : "none",
          display: "flex",
          alignItems: "center",
          padding: `0 ${lerp(26, 0, morph)}px`,
          boxSizing: "border-box",
          overflow: "hidden",
        }}
      >
        <div style={{ fontSize: 24, fontWeight: 700, color: "#e8e8e8", whiteSpace: "nowrap", opacity: (1 - flyT) * (1 - morph), transform: `translate(${flyT * 500}px, ${-flyT * 250}px) rotate(${-flyT * 9}deg)` }}>
          Which model fits my idea?
        </div>
        <Img src={staticFile("vibeaha/shotcraft/logo.png")} style={{ position: "absolute", inset: 18, width: 136, height: 136, objectFit: "contain", opacity: interpolate(morph, [0.6, 1], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }), transform: `scale(${lerp(0.7, 1, morph)})` }} />
      </div>

      {drops.map((drop) => {
        const p = spring({ frame: Math.max(0, frame - drop.start), fps, config: { damping: 12, stiffness: 110, mass: 0.85 } });
        return frame >= drop.start ? <div key={drop.start} style={{ position: "absolute", left: drop.x, top: lerp(-180, drop.y, p), width: drop.w, height: drop.h, borderRadius: Math.min(drop.w, drop.h) / 2, background: drop.color, boxShadow: `0 0 32px ${drop.color}66` }} /> : null;
      })}

      <div style={{ position: "absolute", left: cursorX, top: cursorY, width: 0, height: 0, borderLeft: "13px solid transparent", borderRight: "13px solid transparent", borderBottom: "34px solid #fff", transform: "rotate(-35deg)", opacity: cursorOpacity }} />

      <div style={{ position: "absolute", left: 38, right: 38, top: 620, opacity: ctaIn, transform: `translateY(${(1 - ctaIn) * 60}px)` }}>
        <div style={{ fontSize: 64, lineHeight: 0.98, fontWeight: 900, letterSpacing: 0 }}>
          COMPARE
          <br />
          BEFORE YOU
          <br />
          <span style={{ color: GOLD }}>CREATE.</span>
        </div>
        <div style={{ marginTop: 45, width: "100%", height: 2, background: "rgba(255,255,255,.2)" }} />
        <div style={{ marginTop: 22, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ fontSize: 18, color: "#c8c8c8", fontWeight: 700 }}>Stop paying to guess.</span>
          <span style={{ fontSize: 18, color: GOLD, fontWeight: 900 }}>VIBEAHA.COM</span>
        </div>
      </div>
      <Grain />
    </AbsoluteFill>
  );
};

const CutFlash: React.FC<{ at: number; color?: string }> = ({ at, color = "#fff" }) => {
  const frame = useCurrentFrame();
  const distance = Math.abs(frame - at);
  const opacity = distance > 2 ? 0 : [0.12, 0.3, 0.52][2 - distance];
  return opacity > 0 ? <AbsoluteFill style={{ background: color, opacity, pointerEvents: "none" }} /> : null;
};

export const VibeAhaShotcraft: React.FC = () => (
  <AbsoluteFill style={{ background: "#0a0a0a" }}>
    <Audio src={staticFile("vibeaha/shotcraft/music.m4a")} volume={0.125} />

    <Sequence from={0} durationInFrames={84}><HookScene /></Sequence>
    <Sequence from={84} durationInFrames={126}><WorkspaceScene /></Sequence>
    <Sequence from={210} durationInFrames={96}><GrazeProofScene /></Sequence>
    <Sequence from={306} durationInFrames={99}><ModelMorphScene /></Sequence>
    <Sequence from={405} durationInFrames={150}><OfferScene /></Sequence>
    <Sequence from={555} durationInFrames={120}><CtaScene /></Sequence>

    {[
      { from: 0, src: "01.wav", duration: 60 },
      { from: 84, src: "02.wav", duration: 120 },
      { from: 210, src: "03.wav", duration: 108 },
      { from: 405, src: "04.wav", duration: 120 },
      { from: 555, src: "05.wav", duration: 90 },
    ].map((voice) => (
      <Sequence key={voice.src} from={voice.from} durationInFrames={voice.duration}>
        <Audio src={staticFile(`vibeaha/shotcraft/voice/${voice.src}`)} volume={1} />
      </Sequence>
    ))}

    {[
      { from: 34, src: "sweep.mp3", volume: 0.38, duration: 24 },
      { from: 40, src: "impact.mp3", volume: 0.48, duration: 38 },
      { from: 84, src: "sparkle.mp3", volume: 0.28, duration: 42 },
      { from: 210, src: "sweep.mp3", volume: 0.32, duration: 30 },
      { from: 324, src: "switch.mp3", volume: 0.5, duration: 18 },
      { from: 405, src: "switch.mp3", volume: 0.42, duration: 18 },
      { from: 432, src: "switch.mp3", volume: 0.38, duration: 18 },
      { from: 462, src: "switch.mp3", volume: 0.38, duration: 18 },
      { from: 555, src: "sweep.mp3", volume: 0.34, duration: 26 },
      { from: 577, src: "switch.mp3", volume: 0.42, duration: 16 },
      { from: 632, src: "sparkle.mp3", volume: 0.28, duration: 42 },
    ].map((sfx, index) => (
      <Sequence key={`${sfx.from}-${index}`} from={sfx.from} durationInFrames={sfx.duration}>
        <Audio src={staticFile(`vibeaha/shotcraft/sfx/${sfx.src}`)} volume={sfx.volume} />
      </Sequence>
    ))}

    <CutFlash at={84} color={GOLD} />
    <CutFlash at={210} />
    <CutFlash at={306} color={BLUE} />
    <CutFlash at={405} color={GREEN} />
    <CutFlash at={555} color={GOLD} />
  </AbsoluteFill>
);
