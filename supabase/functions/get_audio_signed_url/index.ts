import { serve } from "https://deno.land/std@0.224.0/http/server.ts";
import { createClient } from "npm:@supabase/supabase-js@2";

const SUPABASE_URL = Deno.env.get("VM_SUPABASE_URL") ?? "";
const SUPABASE_SECRET_KEY = Deno.env.get("VM_SUPABASE_SECRET_KEY") ?? "";
const BUCKET_ID = "voice_messages";
const SIGNED_URL_TTL_SECONDS = 60;

function jsonResponse(
  status: number,
  body: Record<string, unknown>,
): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json",
      "Access-Control-Allow-Origin": "*",
    },
  });
}

function getObjectPath(path: string): string {
  if (path.startsWith(`${BUCKET_ID}/`)) {
    return path.slice(BUCKET_ID.length + 1);
  }
  return path;
}

serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response(null, {
      status: 204,
      headers: {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "authorization, content-type, apikey",
      },
    });
  }

  if (req.method !== "GET") {
    return jsonResponse(405, { error: "method_not_allowed" });
  }

  if (!SUPABASE_URL || !SUPABASE_SECRET_KEY) {
    return jsonResponse(500, { error: "missing_env" });
  }

  const authHeader = req.headers.get("Authorization");
  if (!authHeader) {
    return jsonResponse(401, { error: "missing_authorization" });
  }

  if (!authHeader.toLowerCase().startsWith("bearer ")) {
    return jsonResponse(401, { error: "invalid_authorization_format" });
  }

  const token = authHeader.slice("bearer ".length).trim();

  const messageId = new URL(req.url).searchParams.get("message_id");
  if (!messageId) {
    return jsonResponse(400, { error: "missing_message_id" });
  }

  const serviceClient = createClient(SUPABASE_URL, SUPABASE_SECRET_KEY);

  const { data: userData, error: userError } = await serviceClient.auth
    .getUser(token);
  if (userError || !userData?.user) {
    return jsonResponse(401, { error: "invalid_token" });
  }

  const actorUserId = userData.user.id;

  const { data: message } = await serviceClient
    .from("messages")
    .select(
      "id,resident_id,contact_user_id,audio_storage_path,residents(care_home_id,active)",
    )
    .eq("id", messageId)
    .maybeSingle();

  if (!message || !message.residents?.care_home_id) {
    return jsonResponse(404, { error: "message_not_found" });
  }

  const careHomeId = message.residents.care_home_id;

  const { data: roleRow } = await serviceClient
    .from("care_home_users")
    .select("id")
    .eq("auth_user_id", actorUserId)
    .eq("care_home_id", careHomeId)
    .eq("active", true)
    .maybeSingle();

  const isCareHomeUser = !!roleRow;
  const actorRole = isCareHomeUser ? "care_home" : "family";

  if (!isCareHomeUser) {
    if (message.contact_user_id !== actorUserId) {
      await serviceClient.from("security_events").insert({
        care_home_id: careHomeId,
        actor_user_id: actorUserId,
        actor_role: actorRole,
        event_type: "ACCESS_DENIED:not_message_contact",
        resident_id: message.resident_id,
      });
      return jsonResponse(403, { error: "access_denied" });
    }

    const { data: accessRow } = await serviceClient
      .from("family_contacts")
      .select(
        "id,active,care_home_id,family_contact_access(active,resident_id)",
      )
      .eq("auth_user_id", actorUserId)
      .maybeSingle();

    const linkActive = accessRow?.family_contact_access?.some((link) =>
      link.resident_id === message.resident_id && link.active === true
    );

    if (
      !accessRow ||
      accessRow.care_home_id !== careHomeId ||
      accessRow.active !== true ||
      message.residents.active !== true ||
      !linkActive
    ) {
      await serviceClient.from("security_events").insert({
        care_home_id: careHomeId,
        actor_user_id: actorUserId,
        actor_role: actorRole,
        event_type: "ACCESS_DENIED:inactive_or_unlinked",
        resident_id: message.resident_id,
      });
      return jsonResponse(403, { error: "access_denied" });
    }
  }
  const objectPath = getObjectPath(message.audio_storage_path);

  const { data: signed, error: signedError } = await serviceClient.storage
    .from(BUCKET_ID)
    .createSignedUrl(objectPath, SIGNED_URL_TTL_SECONDS);

  if (signedError || !signed?.signedUrl) {
    await serviceClient.from("security_events").insert({
      care_home_id: careHomeId,
      actor_user_id: actorUserId,
      actor_role: actorRole,
      event_type: "ACCESS_DENIED:sign_failed",
      resident_id: message.resident_id,
    });
    return jsonResponse(500, { error: "sign_failed" });
  }

  await serviceClient.from("security_events").insert({
    care_home_id: careHomeId,
    actor_user_id: actorUserId,
    actor_role: actorRole,
    event_type: "SIGNED_URL_ISSUED",
    resident_id: message.resident_id,
  });

  return jsonResponse(200, {
    signed_url: signed.signedUrl,
    expires_in: SIGNED_URL_TTL_SECONDS,
  });
});
