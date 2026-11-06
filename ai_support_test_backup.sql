--
-- PostgreSQL database dump
--

\restrict tYmZTM0D05ua5WpA72pW4M99eS9BeaZQHiHZaZKs82l5FjiLhUk0VEPHrbLCGeg

-- Dumped from database version 16.15 (Debian 16.15-1.pgdg12+2)
-- Dumped by pg_dump version 16.15 (Debian 16.15-1.pgdg12+2)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: conversations; Type: TABLE; Schema: public; Owner: app_user
--

CREATE TABLE public.conversations (
    id character varying(36) NOT NULL,
    user_id character varying(36) NOT NULL,
    title character varying(255) DEFAULT 'Support Ticket'::character varying NOT NULL,
    status character varying(50) DEFAULT 'active'::character varying NOT NULL,
    priority character varying(50) DEFAULT 'normal'::character varying NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


ALTER TABLE public.conversations OWNER TO app_user;

--
-- Name: messages; Type: TABLE; Schema: public; Owner: app_user
--

CREATE TABLE public.messages (
    id character varying(36) NOT NULL,
    conversation_id character varying(36) NOT NULL,
    role character varying(50) NOT NULL,
    content text NOT NULL,
    sequence_number integer NOT NULL,
    token_count integer DEFAULT 0 NOT NULL,
    metadata_json json,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


ALTER TABLE public.messages OWNER TO app_user;

--
-- Name: users; Type: TABLE; Schema: public; Owner: app_user
--

CREATE TABLE public.users (
    id character varying(36) NOT NULL,
    email character varying(255) NOT NULL,
    hashed_password character varying(255) NOT NULL,
    full_name character varying(255),
    role character varying(50) DEFAULT 'customer'::character varying NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


ALTER TABLE public.users OWNER TO app_user;

--
-- Data for Name: conversations; Type: TABLE DATA; Schema: public; Owner: app_user
--

COPY public.conversations (id, user_id, title, status, priority, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: messages; Type: TABLE DATA; Schema: public; Owner: app_user
--

COPY public.messages (id, conversation_id, role, content, sequence_number, token_count, metadata_json, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: app_user
--

COPY public.users (id, email, hashed_password, full_name, role, is_active, created_at, updated_at) FROM stdin;
\.


--
-- Name: conversations conversations_pkey; Type: CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.conversations
    ADD CONSTRAINT conversations_pkey PRIMARY KEY (id);


--
-- Name: messages messages_pkey; Type: CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.messages
    ADD CONSTRAINT messages_pkey PRIMARY KEY (id);


--
-- Name: messages uq_conversation_sequence; Type: CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.messages
    ADD CONSTRAINT uq_conversation_sequence UNIQUE (conversation_id, sequence_number);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: ix_conversation_sequence; Type: INDEX; Schema: public; Owner: app_user
--

CREATE INDEX ix_conversation_sequence ON public.messages USING btree (conversation_id, sequence_number);


--
-- Name: ix_conversations_status; Type: INDEX; Schema: public; Owner: app_user
--

CREATE INDEX ix_conversations_status ON public.conversations USING btree (status);


--
-- Name: ix_conversations_user_id; Type: INDEX; Schema: public; Owner: app_user
--

CREATE INDEX ix_conversations_user_id ON public.conversations USING btree (user_id);


--
-- Name: ix_messages_conversation_id; Type: INDEX; Schema: public; Owner: app_user
--

CREATE INDEX ix_messages_conversation_id ON public.messages USING btree (conversation_id);


--
-- Name: ix_users_email; Type: INDEX; Schema: public; Owner: app_user
--

CREATE UNIQUE INDEX ix_users_email ON public.users USING btree (email);


--
-- Name: conversations conversations_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.conversations
    ADD CONSTRAINT conversations_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: messages messages_conversation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: app_user
--

ALTER TABLE ONLY public.messages
    ADD CONSTRAINT messages_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES public.conversations(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict tYmZTM0D05ua5WpA72pW4M99eS9BeaZQHiHZaZKs82l5FjiLhUk0VEPHrbLCGeg

