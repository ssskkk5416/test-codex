#!/usr/bin/env python3
"""Generate a celebratory beat for GPT-5 using beatbot."""

from beatbot import Beat, Kick, Snare, HiHat


def make_gpt5_beat(output_file: str = "gpt5_celebration.wav") -> None:
    """Create and export a celebratory beat for GPT-5."""
    bpm = 120
    beat = Beat(bpm=bpm, bars=4)
    beat.add_track(Kick(pattern="x---x---x---x---"))
    beat.add_track(Snare(pattern="----x-------x---"))
    beat.add_track(HiHat(pattern="x-x-x-x-x-x-x-x-"))
    beat.render(output_file)


if __name__ == "__main__":
    make_gpt5_beat()
