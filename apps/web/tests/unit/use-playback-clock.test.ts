/**
 * The test of the clock of the playback.
 *
 * Why this test exists: the playback advances the recording by itself, and the rule that says how it advances has to
 * hold. The interval the browser waits between two events is the interval of the caller divided by the speed, so a
 * speed of four advances four times faster than a speed of one. And the position the clock advances is the position of
 * the state of the reader, never a copy the clock keeps for itself, because a clock that carries a position of its own
 * shows a recording that is not the one the machine is reading.
 *
 * Why the clock is rendered and not called: the module exposes the clock as a hook, and the interval is computed
 * inside it, so the only way to observe the interval and the position is to run the hook against a fake clock.
 *
 * Every case runs with no key and no network: the clock only asks the browser to wait, and the fake clock of the
 * runtime is the browser of the case.
 */

import { act, render } from "@testing-library/react";
import { createElement } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { usePlaybackClock } from "@/features/replay/usePlaybackClock";
import type { ReplayPhase } from "@/features/replay/ReplayProvider";
import type { PlaybackSpeed } from "@/lib/state/urlState";

/** The interval the browser waits between two events at the speed of one, in milliseconds. */
const INTERVAL_MS = 100;

/** The number of events of the recording of the case, big enough to never reach the end. */
const TOTAL = 1000;

/**
 * The properties of the harness of the case.
 */
interface HarnessProps {
  /** The speed the playback runs at. */
  readonly speed: PlaybackSpeed;
  /** The position of the state of the reader, the one the clock has to advance. */
  readonly position: number;
  /** Where the reading of the recording stands. */
  readonly phase?: ReplayPhase;
  /** The interval the browser waits between two events at the speed of one. */
  readonly intervalMs?: number;
  /** Called with the position that comes next. */
  readonly onTick: (position: number) => void;
}

/**
 * The harness of the case: it drives the clock with the position of the state and it writes nothing itself.
 *
 * Why the position is a property and not a state of the harness: the rule is that the clock reads the position of the
 * state of the reader, so the case has to be able to move that position from the outside and to see what the clock
 * does next.
 *
 * Why the interval is a property too: the rule of the floor of the interval is about an interval that is small, and a
 * case that cannot change the interval of the harness can never drive the clock below the floor.
 */
function Harness(props: HarnessProps): null {
  usePlaybackClock({
    phase: props.phase ?? "playing",
    position: props.position,
    total: TOTAL,
    speed: props.speed,
    intervalMs: props.intervalMs ?? INTERVAL_MS,
    onTick: props.onTick,
    onComplete: () => {},
  });
  return null;
}

/**
 * Renders the clock with the given speed and position.
 *
 * Why the case renders it again with another position: the clock must follow the state of the reader, and the only way
 * to prove it is to move the position of the state and to watch what the clock reports next.
 */
function renderClock(speed: PlaybackSpeed, position: number, onTick: (position: number) => void) {
  return render(
    createElement(Harness, {
      speed,
      position,
      onTick,
    }),
  );
}

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("the clock of the playback", () => {
  it("waits four times less at the speed of four", async () => {
    // It proves that the speed divides the interval of the caller: at the speed of one the clock advances once every
    // 100 milliseconds, and at the speed of four it advances four times in the same span of time.
    vi.useFakeTimers();
    const onTick = vi.fn();
    const { rerender } = renderClock(1, 0, onTick);

    await act(async () => {
      vi.advanceTimersByTime(400);
    });
    const atTheNormalSpeed = onTick.mock.calls.length;
    expect(atTheNormalSpeed).toBe(4);

    onTick.mockClear();
    rerender(createElement(Harness, { speed: 4, position: 0, onTick }));

    await act(async () => {
      vi.advanceTimersByTime(400);
    });
    const atTheFastSpeed = onTick.mock.calls.length;
    expect(atTheFastSpeed).toBe(16);
    expect(atTheFastSpeed).toBe(4 * atTheNormalSpeed);
  });

  it("advances the position of the state of the reader and not a copy of its own", async () => {
    // It proves that the position the clock reports is the position of the state plus one, so that the recording the
    // visitor sees is the recording the machine is reading.
    vi.useFakeTimers();
    const onTick = vi.fn();
    const { rerender } = renderClock(1, 5, onTick);

    await act(async () => {
      vi.advanceTimersByTime(100);
    });
    expect(onTick).toHaveBeenCalledTimes(1);
    expect(onTick).toHaveBeenCalledWith(6);

    // The reader moves the position of the state, and the clock follows the new position instead of the one it saw
    // before.
    onTick.mockClear();
    rerender(createElement(Harness, { speed: 1, position: 9, onTick }));

    await act(async () => {
      vi.advanceTimersByTime(100);
    });
    expect(onTick).toHaveBeenCalledTimes(1);
    expect(onTick).toHaveBeenCalledWith(10);
  });

  it("does not run at all when the recording does not play", async () => {
    // It proves that the clock only moves the recording while the visitor asked for it to play.
    vi.useFakeTimers();
    const onTick = vi.fn();
    render(
      createElement(Harness, {
        speed: 1,
        position: 0,
        phase: "ready",
        onTick,
      }),
    );

    await act(async () => {
      vi.advanceTimersByTime(1000);
    });
    expect(onTick).not.toHaveBeenCalled();
  });

  it("never moves the recording when the visitor asked for less motion", async () => {
    // It proves that the preference for less motion stops the CLOCK itself and not only the control of the playback:
    // a recording that moves by itself is an animation, and a visitor who asked the browser for less motion asked for
    // the recording to wait for them.
    //
    // Why the preference is stubbed: jsdom has no media query at all, so the preference of the visitor is unknown to
    // the clock unless the case says what it is.
    vi.stubGlobal(
      "matchMedia",
      vi.fn((query: string) => ({
        matches: true,
        media: query,
        onchange: null,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    );

    vi.useFakeTimers();
    const onTick = vi.fn();
    render(
      createElement(Harness, {
        speed: 1,
        position: 0,
        phase: "playing",
        onTick,
      }),
    );

    await act(async () => {
      vi.advanceTimersByTime(5000);
    });
    expect(onTick).not.toHaveBeenCalled();
  });

  it("never waits less than sixteen milliseconds between two events", async () => {
    // It proves that the interval the clock waits has a floor of sixteen milliseconds, whatever the speed is.
    //
    // Why the interval of the case is four milliseconds and the speed is four: the quotient of the two is one
    // millisecond, which is under the floor, so a clock without the floor would wait one millisecond between two
    // events and a clock with the floor waits sixteen. The case watches the clock from the outside, so it sees the
    // difference without reading the private constant of the module.
    vi.useFakeTimers();
    const onTick = vi.fn();
    render(
      createElement(Harness, {
        speed: 4,
        position: 0,
        intervalMs: 4,
        onTick,
      }),
    );

    // fifteen milliseconds are not enough: a clock that waited one millisecond would already have advanced
    await act(async () => {
      vi.advanceTimersByTime(15);
    });
    expect(onTick).not.toHaveBeenCalled();

    // the sixteenth millisecond is the wait: the clock advances exactly once
    await act(async () => {
      vi.advanceTimersByTime(1);
    });
    expect(onTick).toHaveBeenCalledTimes(1);
    expect(onTick).toHaveBeenCalledWith(1);
  });
});
