import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;
import java.io.*;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public class LocalGigsServer {
    private static final Map<Long, Map<String,Object>> gigs = new ConcurrentHashMap<>();
    private static final Map<Long, Map<String,Object>> applications = new ConcurrentHashMap<>();
    private static final AtomicLong gigIds = new AtomicLong(1), appIds = new AtomicLong(1);

    public static void main(String[] args) throws IOException {
        seed();
        HttpServer server = HttpServer.create(new InetSocketAddress(8080), 0);
        server.createContext("/api/gigs", LocalGigsServer::handleGigs);
        server.createContext("/api/applications", LocalGigsServer::handleApplications);
        server.createContext("/api/organizer/applications", LocalGigsServer::handleOrganizerApplications);
        server.createContext("/api/decisions/evaluate", ex -> {
            cors(ex); if (options(ex)) return;
            Map<String,String> d = parseJson(readBody(ex));
            int age = integer(d.get("age"), 18), min = integer(d.get("minAge"), 18);
            sendJson(ex, 200, obj(Map.of("decision", age >= min ? "ELIGIBLE_FOR_REVIEW" : "NOT_ELIGIBLE", "reason", "Demo rule: age compared with listing minimum. This is not a Strands Decider 2B response.")));
        });
        server.createContext("/", LocalGigsServer::staticFiles);
        server.setExecutor(null); server.start();
        System.out.println("LocalGigs server running at http://localhost:8080");
        System.out.println("Demo only: data is stored in memory and resets when the server stops.");
    }

    private static void seed() {
        addGig(Map.of("title","Community Library Book Fair Assistance","company","City Youth Foundation","category","Event Support","location","Central Library Hall","date","2026-11-05","duration","4 hours","pay","₹700","minAge","18","description","Organize books, help with registration, and guide visitors."));
        addGig(Map.of("title","Tech Fest Registration Desk Support","company","Metro Innovation Hub","category","Education & Tech","location","Convention Center, Block B","date","2026-11-12","duration","6 hours","pay","₹1,200","minAge","18","description","Greet participants, check tickets, and distribute ID tags."));
    }
    private static Map<String,Object> addGig(Map<String,String> d) {
        long id = gigIds.getAndIncrement(); Map<String,Object> g = new LinkedHashMap<>();
        g.put("gigId",id); g.put("title",d.getOrDefault("title","Untitled Gig")); g.put("company",d.getOrDefault("company","Local Organizer"));
        g.put("category",d.getOrDefault("category","General")); g.put("location",d.getOrDefault("location","Local Area")); g.put("date",d.getOrDefault("date","TBD"));
        g.put("duration",d.getOrDefault("duration","4 hours")); g.put("pay",d.getOrDefault("pay","₹500")); g.put("minAge",integer(d.get("minAge"),18));
        g.put("description",d.getOrDefault("description","No description provided.")); g.put("status","Active"); gigs.put(id,g); return g;
    }
    private static void handleGigs(HttpExchange ex) throws IOException {
        cors(ex); if(options(ex)) return; String method=ex.getRequestMethod();
        if(method.equals("GET")) sendJson(ex,200,array(gigs.values()));
        else if(method.equals("POST")) { Map<String,String> d=parseJson(readBody(ex)); if(d.getOrDefault("title","").isBlank()) {sendJson(ex,400,"{\"error\":\"Title is required\"}");return;} sendJson(ex,201,obj(addGig(d))); }
        else sendJson(ex,405,"{\"error\":\"Method not allowed\"}");
    }
    private static void handleApplications(HttpExchange ex) throws IOException {
        cors(ex); if(options(ex)) return; String method=ex.getRequestMethod();
        if(method.equals("GET")) {sendJson(ex,200,array(applications.values()));return;}
        if(!method.equals("POST")){sendJson(ex,405,"{\"error\":\"Method not allowed\"}");return;}
        Map<String,String>d=parseJson(readBody(ex)); long gid=longValue(d.get("gigId"),-1); Map<String,Object>g=gigs.get(gid);
        if(g==null){sendJson(ex,400,"{\"error\":\"Please select a valid gig\"}");return;}
        int age=integer(d.get("age"),18), min=(Integer)g.get("minAge"); String decision=age>=min?"ELIGIBLE_FOR_REVIEW":"NOT_ELIGIBLE";
        Map<String,Object>a=new LinkedHashMap<>(); a.put("applicationId",appIds.getAndIncrement());a.put("gigId",gid);a.put("gigTitle",g.get("title"));a.put("company",g.get("company"));
        a.put("userName",d.getOrDefault("userName","Applicant"));a.put("userAge",age);a.put("eligibilityDecision",decision);a.put("status","Submitted");a.put("submittedAt",new Date().toString());
        a.put("decisionNote","Demo age-rule check only; not an actual Strands Decider 2B result."); applications.put((Long)a.get("applicationId"),a); sendJson(ex,201,obj(a));
    }
    private static void handleOrganizerApplications(HttpExchange ex) throws IOException {
        cors(ex); if(options(ex)) return; String path=ex.getRequestURI().getPath();
        if(ex.getRequestMethod().equals("PATCH") && path.matches("/api/organizer/applications/\\d+/status")) {
            String[] parts=path.split("/"); long id=longValue(parts[parts.length-2],-1); Map<String,Object>a=applications.get(id); Map<String,String>d=parseJson(readBody(ex));
            String status=d.getOrDefault("status",""); if(a==null || !Set.of("Shortlisted","Accepted","Rejected").contains(status)){sendJson(ex,400,"{\"error\":\"Invalid application or status\"}");return;}
            a.put("status",status); sendJson(ex,200,obj(a)); return;
        }
        if(ex.getRequestMethod().equals("GET")){sendJson(ex,200,array(applications.values()));return;} sendJson(ex,405,"{\"error\":\"Method not allowed\"}");
    }
    private static void staticFiles(HttpExchange ex) throws IOException {
        String path=ex.getRequestURI().getPath(); if(path.equals("/"))path="/index.html";
        Path root=Paths.get("public").toAbsolutePath().normalize(); Path file=root.resolve(path.substring(1)).normalize();
        if(!file.startsWith(root) || !Files.isRegularFile(file)){byte[]b="Not found".getBytes(StandardCharsets.UTF_8);ex.sendResponseHeaders(404,b.length);try(OutputStream o=ex.getResponseBody()){o.write(b);}return;}
        String type=Files.probeContentType(file); if(type==null) type="application/octet-stream"; if(file.toString().endsWith(".js"))type="text/javascript; charset=UTF-8"; if(file.toString().endsWith(".css"))type="text/css; charset=UTF-8"; if(file.toString().endsWith(".html"))type="text/html; charset=UTF-8";
        byte[]b=Files.readAllBytes(file);ex.getResponseHeaders().set("Content-Type",type);ex.sendResponseHeaders(200,b.length);try(OutputStream o=ex.getResponseBody()){o.write(b);}
    }
    private static void cors(HttpExchange ex){ex.getResponseHeaders().set("Access-Control-Allow-Origin","*");ex.getResponseHeaders().set("Access-Control-Allow-Methods","GET, POST, PATCH, OPTIONS");ex.getResponseHeaders().set("Access-Control-Allow-Headers","Content-Type");}
    private static boolean options(HttpExchange ex)throws IOException{if(ex.getRequestMethod().equals("OPTIONS")){ex.sendResponseHeaders(204,-1);ex.close();return true;}return false;}
    private static String readBody(HttpExchange ex)throws IOException{return new String(ex.getRequestBody().readAllBytes(),StandardCharsets.UTF_8);}
    private static void sendJson(HttpExchange ex,int status,String s)throws IOException{byte[]b=s.getBytes(StandardCharsets.UTF_8);ex.getResponseHeaders().set("Content-Type","application/json; charset=UTF-8");ex.sendResponseHeaders(status,b.length);try(OutputStream o=ex.getResponseBody()){o.write(b);}}
    private static int integer(String s,int fallback){try{return Integer.parseInt(s);}catch(Exception e){return fallback;}}
    private static long longValue(String s,long fallback){try{return Long.parseLong(s);}catch(Exception e){return fallback;}}
    private static String array(Collection<Map<String,Object>> values){StringJoiner j=new StringJoiner(",","[","]");for(Map<String,Object>m:values)j.add(obj(m));return j.toString();}
    private static String obj(Map<String,?> m){StringJoiner j=new StringJoiner(",","{","}");for(var e:m.entrySet())j.add(quote(e.getKey())+":"+jsonValue(e.getValue()));return j.toString();}
    private static String jsonValue(Object v){if(v==null)return"null";if(v instanceof Number||v instanceof Boolean)return v.toString();return quote(v.toString());}
    private static String quote(String s){return "\""+s.replace("\\","\\\\").replace("\"","\\\"").replace("\n","\\n").replace("\r","\\r").replace("\t","\\t")+"\"";}
    private static Map<String,String> parseJson(String json){Map<String,String> out=new HashMap<>();Matcher m=Pattern.compile("\\\"((?:\\\\.|[^\\\"\\\\])*)\\\"\\s*:\\s*(\\\"(?:\\\\.|[^\\\"\\\\])*\\\"|-?\\d+(?:\\.\\d+)?|true|false|null)").matcher(json);while(m.find()){String k=unescape(m.group(1)),v=m.group(2);if(v.startsWith("\""))v=unescape(v.substring(1,v.length()-1));out.put(k,v.equals("null")?"":v);}return out;}
    private static String unescape(String s){return s.replace("\\\"","\"").replace("\\n","\n").replace("\\r","\r").replace("\\t","\t").replace("\\\\","\\");}
}
