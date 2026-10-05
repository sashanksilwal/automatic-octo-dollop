package edu.purdue.cs536.stream;

import org.junit.Test;
import static org.junit.Assert.*;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.concurrent.*;

public class StreamingTest {
    private Frame frame(long sequence) { return new Frame("test-source",sequence,123,456,1,1,new byte[]{-1,-40,0,1,-1,-39}); }

    @Test public void fragmentedReadPreservesSourceMetadata() throws Exception {
        ByteArrayOutputStream bytes=new ByteArrayOutputStream(); Mjpeg.write(bytes,frame(9));
        InputStream fragmented=new FilterInputStream(new ByteArrayInputStream(bytes.toByteArray())) {
            @Override public int read(byte[] b,int offset,int length) throws IOException { return super.read(b,offset,Math.min(1,length)); }
        };
        Frame result=Mjpeg.read(fragmented);
        assertEquals(9,result.sequence);assertEquals("test-source",result.session);assertEquals(123,result.captureMonoNs);
        assertArrayEquals(frame(9).jpeg,result.jpeg);
    }
    @Test public void rejectsOversizedAndTruncatedFrames() throws Exception {
        ByteArrayOutputStream bytes=new ByteArrayOutputStream(); Mjpeg.write(bytes,frame(1));
        byte[] valid=bytes.toByteArray();
        try { Mjpeg.read(new ByteArrayInputStream(valid,0,valid.length-3)); fail("Truncation accepted"); }
        catch(EOFException expected) { }
        String oversized=new String(valid,StandardCharsets.ISO_8859_1).replace("Content-Length: 6","Content-Length: 999999999");
        try { Mjpeg.read(new ByteArrayInputStream(oversized.getBytes(StandardCharsets.ISO_8859_1))); fail("Oversize accepted"); }
        catch(IOException expected) { assertTrue(expected.getMessage().contains("length")); }
    }
    @Test public void latestSlotSkipsBacklogAndSuppressesReconnectDuplicates() throws Exception {
        FrameHub hub=new FrameHub(Trace.NONE);
        for(int i=0;i<10000;i++) hub.publish(frame(i));
        assertEquals(9999,hub.next(-1,1).frame.sequence);
        assertFalse(hub.publish(frame(9999))); assertEquals(10000,hub.frames());
        hub.clear("paused"); assertNull(hub.next(-1,1));
        hub.publish(new Frame("restarted",0,1,1,1,1,frame(0).jpeg));
        assertEquals("restarted",hub.next(-1,1).frame.session);
        hub.close(); assertFalse(hub.publish(frame(10000)));
    }
    @Test public void realSocketsAuthenticateAndRelay() throws Exception {
        FrameHub source=new FrameHub(Trace.NONE),destination=new FrameHub(Trace.NONE);
        CountDownLatch arrived=new CountDownLatch(1);
        try(StreamServer server=new StreamServer("127.0.0.1",0,"secret536",source,Trace.NONE)) {
            URL status=new URL("http://127.0.0.1:"+server.port()+"/status");
            HttpURLConnection unauthorized=(HttpURLConnection)status.openConnection();
            assertEquals(401,unauthorized.getResponseCode());unauthorized.disconnect();
            try(StreamClient client=new StreamClient("http://127.0.0.1:"+server.port(),"secret536",new StreamClient.Listener(){
                public void frame(Frame frame){destination.publish(frame);arrived.countDown();}
                public void state(String state){}
            },Trace.NONE)) {
                source.publish(frame(14));client.start();assertTrue(arrived.await(3,TimeUnit.SECONDS));
                assertEquals(14,destination.next(-1,1).frame.sequence);
            }
        } finally {source.close();destination.close();}
    }
    @Test public void serverCloseUnblocksAnIdleReader() throws Exception {
        FrameHub hub=new FrameHub(Trace.NONE);
        StreamServer server=new StreamServer("127.0.0.1",0,"secret536",hub,Trace.NONE);
        HttpURLConnection c=(HttpURLConnection)new URL("http://127.0.0.1:"+server.port()+"/stream").openConnection();
        c.setReadTimeout(1500);c.setRequestProperty("Authorization","Bearer secret536");
        assertEquals(200,c.getResponseCode());server.close();assertEquals(-1,c.getInputStream().read());c.disconnect();hub.close();
    }
    @Test public void csvHasSameColumnsForStateAndFrameEvents() throws Exception {
        File file=File.createTempFile("cs536-trace",".csv");
        try {
            try(CsvTrace trace=new CsvTrace(file)){trace.event("state",null,"ready");trace.event("frame",frame(2),"ok");}
            for(String line:Files.readAllLines(file.toPath()))assertEquals(11,line.split(",",-1).length);
        }finally{file.delete();}
    }
    @Test public void rejectsHeaderInjectionAndUnsafeSourceUrls() throws Exception {
        try { new Frame("source\r\nInjected: bad",1,1,1,1,1,frame(1).jpeg); fail(); }catch(IllegalArgumentException expected){}
        for(String url:new String[]{"file:///etc/passwd","http://user:password@localhost/","http://localhost/stream?token=x"}) {
            try {new StreamClient(url,"secret536",new StreamClient.Listener(){public void frame(Frame f){}public void state(String s){}},Trace.NONE);fail(url);}
            catch(MalformedURLException expected){}
        }
    }
}
