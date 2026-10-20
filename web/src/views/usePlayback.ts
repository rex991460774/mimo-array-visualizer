import { useCallback, useEffect, useRef, useState } from "react";

export const PLAYBACK_SPEEDS = [10, 20, 40] as const;

/** Frame-index playback driven by requestAnimationFrame at a fixed frame rate. */
export function usePlayback(count: number, initialIndex: number) {
  const [index, setIndex] = useState(initialIndex);
  const [playing, setPlaying] = useState(false);
  const [fps, setFps] = useState<number>(PLAYBACK_SPEEDS[1]);
  const indexRef = useRef(index);
  indexRef.current = index;

  // A new spectrum bank (e.g. another FOV) moves the reference frame: stop and
  // return to it instead of keeping a stale index.
  useEffect(() => {
    setPlaying(false);
    setIndex(initialIndex);
  }, [initialIndex, count]);

  useEffect(() => {
    if (!playing || count <= 0) return;
    let frame = 0;
    let last = performance.now();
    let accumulator = 0;
    const tick = (now: number) => {
      accumulator += now - last;
      last = now;
      const interval = 1000 / fps;
      if (accumulator >= interval) {
        const steps = Math.floor(accumulator / interval);
        accumulator -= steps * interval;
        const next = indexRef.current + steps;
        if (next >= count - 1) {
          setIndex(count - 1);
          setPlaying(false);
          return;
        }
        setIndex(next);
      }
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [playing, fps, count]);

  const toggle = useCallback(() => {
    setPlaying((current) => {
      if (!current && indexRef.current >= count - 1) setIndex(0);
      return !current;
    });
  }, [count]);

  const reset = useCallback(() => {
    setPlaying(false);
    setIndex(initialIndex);
  }, [initialIndex]);

  const seek = useCallback(
    (value: number) => {
      setIndex(Math.max(0, Math.min(count - 1, value)));
    },
    [count],
  );

  return { index, seek, playing, setPlaying, toggle, reset, fps, setFps };
}
