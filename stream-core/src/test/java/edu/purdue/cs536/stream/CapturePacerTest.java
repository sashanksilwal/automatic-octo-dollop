package edu.purdue.cs536.stream;
import org.junit.Test;
import static org.junit.Assert.*;

public class CapturePacerTest {
    @Test public void rateConvergesWhenCallbacksDoNotDivideRequestedPeriod() {
        for (int rate : new int[]{15,30,60}) {
            CapturePacer gate=new CapturePacer(8);int count=0;
            for (int i=0;i<rate*30;i++) if(gate.accept(Math.round(i*1e9/rate))) count++;
            assertEquals(240,count);
        }
    }
    @Test public void stallDoesNotQueueCatchupFrames() {
        CapturePacer gate=new CapturePacer(8);
        assertTrue(gate.accept(0));assertFalse(gate.accept(0));
        assertFalse(gate.accept(124_999_999));assertTrue(gate.accept(133_333_333));
        assertTrue(gate.accept(250_000_000));assertTrue(gate.accept(10_000_000_000L));
        assertFalse(gate.accept(10_000_000_000L));assertFalse(gate.accept(10_124_999_999L));
        assertTrue(gate.accept(10_125_000_000L));
    }
    @Test public void slowCameraCannotSupplyMissingFrames() {
        CapturePacer gate=new CapturePacer(8);int count=0;
        for(int i=0;i<150;i++) if(gate.accept(i*200_000_000L)) count++;
        assertEquals(150,count);
    }
    @Test public void nanoTimeWrapPreservesDueComparisons() {
        CapturePacer gate=new CapturePacer(8);long start=Long.MAX_VALUE-40_000_000;
        assertTrue(gate.accept(start));assertFalse(gate.accept(start+100_000_000));
        assertTrue(gate.accept(start+125_000_000));
    }
    @Test(expected=IllegalArgumentException.class) public void invalidRateRejected() {new CapturePacer(0);}
}
