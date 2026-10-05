import edu.purdue.cs536.stream.*;
import java.util.concurrent.CountDownLatch;

/** Runs the phone's real shared Java transport on a JVM for cross-language tests. */
public final class RelayHarness {
    public static void main(String[] args) throws Exception {
        FrameHub hub=new FrameHub(Trace.NONE);
        StreamServer server=new StreamServer("127.0.0.1",0,"relay536",hub,Trace.NONE);
        StreamClient client=new StreamClient(args[0],"source536",new StreamClient.Listener(){
            public void frame(Frame f){hub.publish(f);}
            public void state(String s){hub.clear(s);}
        },Trace.NONE);
        Runtime.getRuntime().addShutdownHook(new Thread(()->{client.close();hub.close();server.close();}));
        client.start();System.out.println(server.port());System.out.flush();
        new CountDownLatch(1).await();
    }
}
