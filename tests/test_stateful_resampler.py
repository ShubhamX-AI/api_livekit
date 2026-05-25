import unittest
import numpy as np
import scipy.signal as sig
import audioop

from src.services.exotel.custom_sip_reach.rtp_bridge import (
    _decode_rtp_payload,
    RTPMediaBridge,
)
from src.services.exotel.custom_sip_reach.config import (
    PCMA_PAYLOAD_TYPE,
    PCMU_PAYLOAD_TYPE,
)


class TestStatefulResampler(unittest.TestCase):
    def test_stateful_upsampling_mathematically(self):
        """Verify that stateful upsampling block-by-block matches continuous upsampling."""
        up = 6
        down = 1
        half_len = 10
        history_len = 2 * half_len  # 20 samples

        # Continuous sine wave
        t = np.arange(1000) / 8000.0
        x = np.sin(2 * np.pi * 440 * t)

        # Reference offline resample
        y_gold = sig.resample_poly(x, up, down)

        # Stateful upsampling simulation
        history = np.zeros(history_len)
        y_stateful = []
        for i in range(0, len(x), 160):
            chunk = x[i:i+160]
            if len(chunk) < 160:
                break
            full_input = np.concatenate([history, chunk])
            history = full_input[-len(history):]
            
            resampled_full = sig.resample_poly(full_input, up, down)
            
            # Extract aligned chunk
            start_idx = (len(history) - half_len) * up
            end_idx = start_idx + len(chunk) * up
            y_stateful.append(resampled_full[start_idx:end_idx])

        y_stateful = np.concatenate(y_stateful)
        y_gold_delayed = np.concatenate([np.zeros(half_len * up), y_gold])[:len(y_stateful)]

        # Test middle section (excluding the global boundaries)
        diff_mid = y_gold_delayed[300:900] - y_stateful[300:900]
        max_err = np.max(np.abs(diff_mid))
        self.assertLess(max_err, 1e-6, f"Max error {max_err} is not close to 0")

    def test_stateful_downsampling_mathematically(self):
        """Verify that stateful downsampling block-by-block matches continuous downsampling."""
        up = 1
        down = 6
        half_len = 10
        history_len = 2 * half_len * down  # 120 samples

        # Continuous high-rate sine wave
        t = np.arange(6000) / 48000.0
        x = np.sin(2 * np.pi * 440 * t)

        # Reference offline downsample
        y_gold = sig.resample_poly(x, up, down)

        # Stateful downsampling simulation
        history = np.zeros(history_len)
        y_stateful = []
        for i in range(0, len(x), 480):
            chunk = x[i:i+480]
            if len(chunk) < 480:
                break
            full_input = np.concatenate([history, chunk])
            history = full_input[-len(history):]
            
            resampled_full = sig.resample_poly(full_input, up, down)
            
            # Extract aligned chunk
            start_idx = (len(history) - half_len * down) // down
            end_idx = start_idx + len(chunk) // down
            y_stateful.append(resampled_full[start_idx:end_idx])

        y_stateful = np.concatenate(y_stateful)
        y_gold_delayed = np.concatenate([np.zeros(half_len), y_gold])[:len(y_stateful)]

        # Test middle section
        diff_mid = y_gold_delayed[50:150] - y_stateful[50:150]
        max_err = np.max(np.abs(diff_mid))
        self.assertLess(max_err, 1e-6, f"Max error {max_err} is not close to 0")

    def test_decode_rtp_payload_stateful(self):
        """Test the actual _decode_rtp_payload implementation handles state correctly."""
        # Generate some dummy PCMA bytes
        samples = np.sin(2 * np.pi * 440 * np.arange(160) / 8000.0)
        pcm16 = (samples * 32767.0).astype(np.int16).tobytes()
        payload = audioop.lin2alaw(pcm16, 2)

        # First packet: None state
        state = (None, None)
        pcm48_1, state_1 = _decode_rtp_payload(payload, PCMA_PAYLOAD_TYPE, state)
        
        self.assertEqual(len(pcm48_1), 160 * 6 * 2)  # 960 samples, 1920 bytes
        self.assertIsNotNone(state_1[0])  # zi is not None
        self.assertEqual(len(state_1[1]), 20)  # history has 20 samples

        # Second packet: Pass previous state
        pcm48_2, state_2 = _decode_rtp_payload(payload, PCMA_PAYLOAD_TYPE, state_1)
        self.assertEqual(len(pcm48_2), 160 * 6 * 2)
        self.assertIsNotNone(state_2[0])
        self.assertEqual(len(state_2[1]), 20)


if __name__ == "__main__":
    unittest.main()
