import edu.purdue.cs536.stream.*;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.security.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicLong;
import javax.net.ssl.*;

/** Transport only: latest-frame phone relay to authenticated WSS. No inference. */
public final class CellularUpload {
    private static final SecureRandom random = new SecureRandom();
    private static String line(InputStream in) throws IOException {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        for (int i=0; i<4096; i++) {
            int b=in.read(); if(b<0) throw new EOFException();
            if(b==10) return new String(out.toByteArray(), StandardCharsets.US_ASCII).trim();
            out.write(b);
        }
        throw new IOException("Header too long");
    }
    static void send(OutputStream out,int opcode,byte[] payload) throws IOException {
        synchronized(out) {
            out.write(0x80|opcode);
            int n=payload.length;
            if(n<126) out.write(0x80|n);
            else if(n<=65535) { out.write(0xfe);out.write(n>>>8);out.write(n); }
            else { out.write(0xff);new DataOutputStream(out).writeLong(n); }
            byte[] mask=new byte[4];random.nextBytes(mask);out.write(mask);
            byte[] block=new byte[8192];
            for(int offset=0;offset<n;offset+=block.length) {
                int count=Math.min(block.length,n-offset);
                for(int i=0;i<count;i++) block[i]=(byte)(payload[offset+i]^mask[(offset+i)%4]);
                out.write(block,0,count);
            }
            out.flush();
        }
    }
    public static void main(String[] args) throws Exception {
        BufferedReader config=new BufferedReader(new InputStreamReader(System.in,StandardCharsets.UTF_8));
        String source=config.readLine(),sourceToken=config.readLine();
        URL destination=new URL(config.readLine()+"/ingest");String token=config.readLine();
        if(!destination.getProtocol().equals("https")||destination.getUserInfo()!=null
            ||token==null||!token.matches("[A-Za-z0-9_-]{32,128}")) throw new IllegalArgumentException();
        CsvTrace trace=new CsvTrace(new File(args[0]));FrameHub hub=new FrameHub(trace);
        StreamClient client=new StreamClient(source,sourceToken,new StreamClient.Listener() {
            public void frame(Frame f){hub.publish(f);}
            public void state(String s){hub.clear(s);}
        },trace);
        ScheduledExecutorService timer=Executors.newSingleThreadScheduledExecutor();
        Runtime.getRuntime().addShutdownHook(new Thread(()->{
            client.close();hub.close();timer.shutdownNow();try{trace.close();}catch(IOException ignored){}
        }));
        client.start();long version=-1;
        while(true) {
            if(hub.next(version,3000)==null) continue;
            SSLSocket socket=(SSLSocket)SSLSocketFactory.getDefault().createSocket();
            ScheduledFuture<?> guard=null;
            try {
                socket.connect(new InetSocketAddress(destination.getHost(),443),10000);
                socket.setSoTimeout(15000);socket.setSendBufferSize(65536);socket.setTcpNoDelay(true);
                SSLParameters params=socket.getSSLParameters();params.setEndpointIdentificationAlgorithm("HTTPS");
                params.setServerNames(Arrays.asList(new SNIHostName(destination.getHost())));
                socket.setSSLParameters(params);socket.startHandshake();
                InputStream in=new BufferedInputStream(socket.getInputStream());
                OutputStream out=new BufferedOutputStream(socket.getOutputStream(),16384);
                byte[] nonce=new byte[16];random.nextBytes(nonce);String key=Base64.getEncoder().encodeToString(nonce);
                String request="GET /ingest HTTP/1.1\r\nHost: "+destination.getHost()+"\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: "+key+"\r\nSec-WebSocket-Version: 13\r\nAuthorization: Bearer "+token+"\r\n\r\n";
                out.write(request.getBytes(StandardCharsets.US_ASCII));out.flush();
                String status=line(in);Map<String,String> headers=new HashMap<>();
                for(int i=0;i<80;i++){String h=line(in);if(h.isEmpty())break;int c=h.indexOf(':');if(c>0)headers.put(h.substring(0,c).toLowerCase(Locale.ROOT),h.substring(c+1).trim());}
                String accept=Base64.getEncoder().encodeToString(MessageDigest.getInstance("SHA-1").digest((key+"258EAFA5-E914-47DA-95CA-C5AB0DC85B11").getBytes(StandardCharsets.US_ASCII)));
                if(!status.startsWith("HTTP/1.1 101 ")||!accept.equals(headers.get("sec-websocket-accept")))throw new IOException("WebSocket handshake rejected");
                trace.event("upload_connected",null,"wss;certificate_and_hostname_verified");
                System.out.println("Live WSS bridge connected");System.out.flush();
                AtomicLong writingSince=new AtomicLong();
                guard=timer.scheduleAtFixedRate(()->{long started=writingSince.get();if(started!=0&&System.nanoTime()-started>10_000_000_000L)try{socket.close();}catch(IOException ignored){}},1,1,TimeUnit.SECONDS);
                Thread controls=new Thread(()->{
                    try {
                        socket.setSoTimeout(0);
                        DataInputStream data=new DataInputStream(in);
                        while(!socket.isClosed()) {
                            int a=data.readUnsignedByte(),b=data.readUnsignedByte(),n=b&127;
                            if((a&0x80)==0||(b&0x80)!=0||n>125)throw new IOException("Unexpected control frame");
                            byte[] payload=new byte[n];data.readFully(payload);
                            if((a&15)==8)break;
                            if((a&15)==9)send(out,10,payload);
                        }
                    }catch(IOException ignored){}finally{try{socket.close();}catch(IOException ignored){}}
                },"websocket-controls");controls.setDaemon(true);controls.start();
                while(!socket.isClosed()) {
                    FrameHub.Sample sample=hub.next(version,3000);if(sample==null)break;
                    ByteArrayOutputStream encoded=new ByteArrayOutputStream(sample.frame.jpeg.length+512);
                    Mjpeg.write(encoded,sample.frame);
                    writingSince.set(System.nanoTime());send(out,2,encoded.toByteArray());writingSince.set(0);
                    trace.event("frame_uploaded",sample.frame,"skipped="+(version<0?0:Math.max(0,sample.version-version-1)));
                    version=sample.version;
                }
            }catch(IOException e){trace.event("upload_error",null,e.getClass().getSimpleName());System.out.println("Upload reconnect: "+e.getClass().getSimpleName());Thread.sleep(1000);}
            finally{if(guard!=null)guard.cancel(false);socket.close();}
        }
    }
}
